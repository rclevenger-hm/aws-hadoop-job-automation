import base64
import json
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal

from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

from app.validation import ApiError, TERMINAL, canonical, digest, invalid

SERIALIZER = TypeSerializer()


def encode(item):
    return {k: SERIALIZER.serialize(v) for k, v in item.items()}


def plain(value):
    if isinstance(value, Decimal):
        return int(value)
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


def conditional(error):
    return isinstance(error, ClientError) and error.response['Error']['Code'] == 'ConditionalCheckFailedException'


class Store:
    def __init__(self, table, client, queue, queue_url, daily_limit=100, rate_limit=60, retention=30, clock=time.time):
        self.table, self.client, self.queue, self.queue_url = table, client, queue, queue_url
        self.daily_limit, self.rate_limit, self.retention, self.clock = daily_limit, rate_limit, retention, clock
        if not all(isinstance(v, int) and v > 0 for v in [daily_limit, rate_limit, retention]):
            raise ValueError('Limits must be positive integers')

    def now(self):
        return int(self.clock())

    def date(self):
        return datetime.fromtimestamp(self.now(), timezone.utc).strftime('%Y-%m-%d')

    def get(self, tenant, job_id):
        item = self.table.get_item(Key={'pk': tenant, 'sk': f'JOB#{job_id}'}, ConsistentRead=True).get('Item')
        if item and item.get('expires_at', self.now() + 1) > self.now():
            return plain(item)
        return None

    def enqueue(self, job):
        self.queue.send_message(QueueUrl=self.queue_url, MessageBody=canonical({'tenant': job['pk'], 'job_id': job['job_id']}))

    def decorate(self, job):
        if job['status'] in TERMINAL:
            job.pop('active_pk', None)
            job.pop('active_sk', None)
            job['expires_at'] = self.now() + self.retention * 86400
        else:
            job.pop('expires_at', None)
            job['active_pk'] = f"ACTIVE#{job['job_id'][0]}"
            job['active_sk'] = f"{job['next_check']:012d}#{job['job_id']}"
        return job

    def create(self, tenant, job_id, request, profile, step_name):
        existing = self.get(tenant, job_id)
        fingerprint = digest(canonical(request))
        if existing:
            return self.check_replay(existing, fingerprint), False
        job = self.decorate({'pk': tenant, 'sk': f'JOB#{job_id}', 'job_id': job_id, 'request': request, 'profile': profile,
                             'fingerprint': fingerprint, 'step_name': step_name, 'status': 'QUEUED', 'version': 1,
                             'created_at': self.now(), 'updated_at': self.now(), 'next_check': self.now() + 120,
                             'history_pk': tenant, 'history_sk': f'{self.now():012d}#{job_id}'})
        try:
            self.client.transact_write_items(TransactItems=[
                {'Put': {'TableName': self.table.name, 'Item': encode(job), 'ConditionExpression': 'attribute_not_exists(pk)'}},
                {'Update': {'TableName': self.table.name, 'Key': encode({'pk': tenant, 'sk': f'USAGE#{self.date()}'}),
                            'UpdateExpression': 'SET expires_at = :expiry ADD units :one',
                            'ConditionExpression': 'attribute_not_exists(units) OR units < :limit',
                            'ExpressionAttributeValues': encode({':expiry': self.now() + 3 * 86400, ':one': 1, ':limit': self.daily_limit})}},
            ])
        except ClientError as exc:
            if exc.response['Error']['Code'] != 'TransactionCanceledException':
                raise
            existing = self.get(tenant, job_id)
            if existing:
                return self.check_replay(existing, fingerprint), False
            if self.usage(tenant)['jobs'] >= self.daily_limit:
                raise ApiError(429, 'DAILY_LIMIT', 'Daily job allowance exhausted') from exc
            old = self.table.get_item(Key={'pk': tenant, 'sk': f'JOB#{job_id}'}, ConsistentRead=True).get('Item')
            if old:
                raise ApiError(409, 'EXPIRED_KEY', 'Use a fresh idempotency key') from exc
            raise
        return job, True

    @staticmethod
    def check_replay(job, fingerprint):
        if job['fingerprint'] != fingerprint:
            raise ApiError(409, 'IDEMPOTENCY_CONFLICT', 'Key already used with different job inputs')
        return job

    def replace(self, job, **changes):
        updated = self.decorate({**job, **changes, 'version': job['version'] + 1, 'updated_at': self.now()})
        try:
            self.table.put_item(Item=updated, ConditionExpression='#v = :version',
                                ExpressionAttributeNames={'#v': 'version'}, ExpressionAttributeValues={':version': job['version']})
        except ClientError as exc:
            if conditional(exc):
                return None
            raise
        if updated['status'] != job['status']:
            logging.getLogger(__name__).warning(json.dumps({'event': 'job_state', 'job_id': job['job_id'], 'status': updated['status']}))
        return updated

    def request_limit(self, tenant):
        try:
            self.table.update_item(Key={'pk': tenant, 'sk': f'RATE#{self.now() // 60}'},
                                   UpdateExpression='SET expires_at = :expiry ADD units :one',
                                   ConditionExpression='attribute_not_exists(units) OR units < :limit',
                                   ExpressionAttributeValues={':expiry': self.now() + 120, ':one': 1, ':limit': self.rate_limit})
        except ClientError as exc:
            if conditional(exc):
                raise ApiError(429, 'RATE_LIMIT', 'Request allowance exhausted; retry in one minute') from exc
            raise

    def usage(self, tenant):
        item = self.table.get_item(Key={'pk': tenant, 'sk': f'USAGE#{self.date()}'}, ConsistentRead=True).get('Item', {})
        return {'date': self.date(), 'jobs': int(item.get('units', 0)), 'limit': self.daily_limit}

    def history(self, tenant, limit=20, cursor=None, status=None):
        signature = digest(canonical({'tenant': tenant, 'status': status}))
        options = {'IndexName': 'history', 'KeyConditionExpression': Key('history_pk').eq(tenant), 'ScanIndexForward': False, 'Limit': limit}
        if cursor:
            try:
                if len(cursor) > 2048:
                    raise ValueError()
                decoded = json.loads(base64.b64decode(cursor, altchars=b'-_', validate=True))
                key = decoded['key']
                if decoded['signature'] != signature or key['pk'] != tenant or key['history_pk'] != tenant or set(key) != {'pk', 'sk', 'history_pk', 'history_sk'} or not all(isinstance(v, str) for v in key.values()):
                    raise ValueError()
                options['ExclusiveStartKey'] = key
            except (ValueError, KeyError, TypeError) as exc:
                raise invalid('Cursor does not match this query') from exc
        page = self.table.query(**options)
        # GSI state may lag. Read authoritative rows before returning status or ownership data.
        jobs = [self.get(tenant, v['job_id']) for v in page.get('Items', [])]
        jobs = [v for v in jobs if v and (not status or v['status'] == status)]
        last = page.get('LastEvaluatedKey')
        token = base64.urlsafe_b64encode(canonical({'key': last, 'signature': signature}).encode()).decode() if last else None
        return jobs, token

    def due(self, shard, limit=25):
        page = self.table.query(IndexName='active', KeyConditionExpression=Key('active_pk').eq(f'ACTIVE#{shard}') & Key('active_sk').lte(f'{self.now():012d}#~'), Limit=limit)
        return page.get('Items', [])

    def claim_poll(self, tenant, job_id):
        job = self.get(tenant, job_id)
        if not job or job['status'] in TERMINAL or job['next_check'] > self.now():
            return None
        return self.replace(job, next_check=self.now() + 120)
