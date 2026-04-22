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
