import base64
import hashlib
import json
import re
from urllib.parse import urlsplit

MAX_BODY = 65536
TERMINAL = frozenset({'SUCCEEDED', 'FAILED', 'CANCELLED', 'NEEDS_REVIEW'})
STATES = TERMINAL | {'QUEUED', 'SUBMITTING', 'SUBMISSION_UNKNOWN', 'SUBMITTED', 'RUNNING', 'CANCEL_REQUESTED'}


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


def invalid(message):
    return ApiError(400, 'INVALID_REQUEST', message)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def principal(event):
    arn = event.get('requestContext', {}).get('identity', {}).get('userArn', '')
    match = re.fullmatch(r'arn:(aws(?:-us-gov|-cn)?):sts::(\d{12}):assumed-role/([^/]+)/[^/]+', arn)
    if match:
        return f'arn:{match[1]}:iam::{match[2]}:role/{match[3]}'
    if re.fullmatch(r'arn:aws(?:-us-gov|-cn)?:iam::\d{12}:(?:role|user)/[A-Za-z0-9+=,.@_/-]+', arn):
        return arn
    raise ApiError(401, 'UNAUTHENTICATED', 'A signed IAM request is required')


def body(event):
    raw = event.get('body')
    if not isinstance(raw, str) or len(raw) > MAX_BODY * 2:
        raise invalid('A JSON body of at most 64 KiB is required')
    try:
        data = base64.b64decode(raw, validate=True) if event.get('isBase64Encoded') else raw.encode('utf-8')
        if len(data) > MAX_BODY:
            raise ApiError(413, 'BODY_TOO_LARGE', 'Body exceeds 64 KiB')
        result = json.loads(data.decode('utf-8'), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError) as exc:
        raise invalid('Body must be valid UTF-8 JSON') from exc
    if not isinstance(result, dict):
        raise invalid('Body must be a JSON object')
    return result


def text(value, field, maximum=4096):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise invalid(f'{field} must be nonblank text, at most {maximum} characters, without controls')
    try:
        value.encode('utf-8')
    except UnicodeError as exc:
        raise invalid(f'{field} must be valid Unicode') from exc
    return value.strip()


def allowed_path(value, prefixes, field):
    value = text(value, field)
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise invalid(f'{field} is not a valid URI') from exc
    if parts.scheme not in {'s3', 'hdfs'} or parts.query or parts.fragment or '%' in value or '\\' in value or any(p in {'.', '..'} for p in parts.path.split('/')):
        raise invalid(f'{field} must be a canonical S3 or HDFS URI')
    if not any(value.startswith(p) and len(value) > len(p) for p in prefixes):
        raise ApiError(403, 'PATH_NOT_ALLOWED', f'{field} is outside the configured prefixes')
    return value


def job_request(payload, profiles, caller):
    if set(payload) - {'profile', 'jar_path', 'job_class', 'input_path', 'output_path', 'arguments'}:
        raise invalid('Unknown request field')
    name = text(payload.get('profile'), 'profile', 40)
    profile = profiles.get(name)
    if not profile or caller not in profile['allowed_principals']:
        raise ApiError(403, 'PROFILE_NOT_ALLOWED', 'Cluster profile is not authorized')
    result = {'profile': name}
    for field, key in [('jar_path', 'jar_prefixes'), ('input_path', 'input_prefixes'), ('output_path', 'output_prefixes')]:
        result[field] = allowed_path(payload.get(field), profile[key], field)
    result['job_class'] = text(payload.get('job_class'), 'job_class')
    if not re.fullmatch(r'[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*', result['job_class'], re.ASCII):
        raise invalid('job_class must be a fully qualified Java class name')
    arguments = payload.get('arguments', [])
    if not isinstance(arguments, list) or len(arguments) > 20:
        raise invalid('arguments must contain at most 20 strings')
    result['arguments'] = [text(v, 'argument', 1024) for v in arguments]
    if sum(len(result[k]) for k in ['jar_path', 'job_class', 'input_path', 'output_path']) + sum(map(len, result['arguments'])) > 10240:
        raise invalid('EMR HadoopJarStep strings exceed 10240 characters')
    if result['input_path'] == result['output_path']:
        raise invalid('Input and output paths must differ')
    return result


def key_id(key, tenant):
    if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{8,128}', key):
        raise invalid('Idempotency-Key must be 8–128 letters, digits, dots, underscores, colons or hyphens')
    return digest(f'{tenant}:{key}')


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value):
        raise invalid('Invalid job identifier')
    return value


def integer(value, default, maximum):
    if value is None:
        return default
    if not re.fullmatch(r'[0-9]+', str(value)) or not 1 <= int(value) <= maximum:
        raise invalid(f'Expected integer from 1 to {maximum}')
    return int(value)
