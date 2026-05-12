import json
import logging
import time
from decimal import Decimal

import boto3
from botocore.config import Config

from app.config import settings
from app.emr import Emr
from app.service import Service, public
from app.store import Store
from app.validation import ApiError, STATES, body, digest, integer, principal

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
_SERVICE = None


def runtime():
    global _SERVICE
    if _SERVICE is None:
        cfg = settings()
        common = Config(connect_timeout=3, read_timeout=5, retries={'total_max_attempts': 3, 'mode': 'standard'})
        # Zero SDK retries on the non-idempotent submission operation, including transport errors.
        emr_config = Config(connect_timeout=3, read_timeout=8, retries={'total_max_attempts': 1, 'mode': 'standard'})
        resource = boto3.resource('dynamodb', config=common)
        store = Store(resource.Table(cfg['table']), boto3.client('dynamodb', config=common), boto3.client('sqs', config=common), cfg['queue'],
                      cfg['daily_limit'], cfg['rate_limit'], cfg['retention'])
        _SERVICE = Service(store, Emr(boto3.client('emr', config=emr_config), boto3.client('s3', config=common)), cfg['profiles'], cfg['prefix'])
    return _SERVICE


def response(status, value, request_id):
    return {'statusCode': status, 'headers': {'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'X-Request-Id': request_id,
                                            **({'Retry-After': '60'} if status == 429 else {})},
            'body': json.dumps(value, default=lambda v: int(v) if isinstance(v, Decimal) else str(v))}


def api_handler(event, context):
    request_id = getattr(context, 'aws_request_id', 'unknown')
    status = 500
    try:
        caller = principal(event)
        service = runtime()
        tenant = digest(caller)
        service.store.request_limit(tenant)
        method, route = event.get('httpMethod'), event.get('resource')
        query = event.get('queryStringParameters') or {}
        job_id = (event.get('pathParameters') or {}).get('job_id')
        result, status = None, 200
        if method == 'POST' and route == '/jobs':
            headers = {k.lower(): v for k, v in (event.get('headers') or {}).items()}
            result, created = service.submit(caller, headers.get('idempotency-key'), body(event))
            status = 202 if created else 200
        elif method == 'GET' and route == '/jobs':
            if query.get('status') and query['status'] not in STATES:
                raise ApiError(400, 'INVALID_STATUS', 'Unknown job status')
            jobs, cursor = service.store.history(tenant, integer(query.get('limit'), 20, 100), query.get('cursor'), query.get('status'))
            result = {'jobs': [public(j) for j in jobs], 'next_cursor': cursor}
        elif method == 'GET' and route == '/jobs/{job_id}':
            result = public(service.owned(caller, job_id))
        elif method == 'POST' and route == '/jobs/{job_id}/cancel':
            result = service.cancel(caller, job_id)
            status = 202 if result['status'] == 'CANCEL_REQUESTED' else 200
        elif method == 'GET' and route == '/jobs/{job_id}/logs':
            result = service.emr.logs(service.owned(caller, job_id), query.get('stream', 'stdout'), integer(query.get('limit'), 16384, 65536))
        elif method == 'GET' and route == '/usage':
            result = service.store.usage(tenant)
        else:
            raise ApiError(404, 'NOT_FOUND', 'Route not found')
        return response(status, result, request_id)
    except ApiError as exc:
        status = exc.status
        result = response(status, {'code': exc.code, 'error': str(exc), 'request_id': request_id}, request_id)
        if exc.code == 'DAILY_LIMIT':
            result['headers']['Retry-After'] = str(86400 - int(time.time()) % 86400)
        return result
    except Exception as exc:
        status = 503
        LOGGER.error(json.dumps({'event': 'api_error', 'request_id': request_id, 'error_type': type(exc).__name__}))
        return response(status, {'code': 'SERVICE_UNAVAILABLE', 'error': 'Service temporarily unavailable', 'request_id': request_id}, request_id)
    finally:
        LOGGER.info(json.dumps({'event': 'api_request', 'request_id': request_id, 'status': status}))


def worker_handler(event, context):
    failures = []
    for record in event.get('Records', []):
        try:
            payload = record['body']
            if not isinstance(payload, str) or len(payload) > 1024:
                raise ValueError('Invalid queue message')
            message = json.loads(payload)
            if not isinstance(message, dict) or set(message) != {'tenant', 'job_id'}:
                raise ValueError('Invalid queue message')
            runtime().process(message)
        except Exception as exc:
            LOGGER.error(json.dumps({'event': 'worker_error', 'error_type': type(exc).__name__}))
            failures.append({'itemIdentifier': record['messageId']})
    return {'batchItemFailures': failures}
