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
