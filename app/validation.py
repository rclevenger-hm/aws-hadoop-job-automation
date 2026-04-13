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
