import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import boto3
import pytest
from moto import mock_aws

from app.config import load_profiles
from app.service import Service
from app.store import Store

CALLER = 'arn:aws:iam::123456789012:role/HadoopConsumer'
OTHER = 'arn:aws:iam::123456789012:role/OtherConsumer'


@pytest.fixture
def profiles():
    return load_profiles(open('examples/profiles.json').read())


@pytest.fixture
def payload():
    return json.load(open('examples/job.json'))


@pytest.fixture
def env(monkeypatch, profiles):
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'testing')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'testing')
    monkeypatch.setenv('AWS_EC2_METADATA_DISABLED', 'true')
    with mock_aws():
        db = boto3.resource('dynamodb', region_name='us-east-1')
        names = ['pk', 'sk', 'history_pk', 'history_sk', 'active_pk', 'active_sk']
        indexes = [{'IndexName': name, 'KeySchema': [{'AttributeName': f'{name}_pk', 'KeyType': 'HASH'}, {'AttributeName': f'{name}_sk', 'KeyType': 'RANGE'}], 'Projection': {'ProjectionType': 'ALL'}} for name in ['history', 'active']]
        table = db.create_table(TableName='jobs', KeySchema=[{'AttributeName': 'pk', 'KeyType': 'HASH'}, {'AttributeName': 'sk', 'KeyType': 'RANGE'}], AttributeDefinitions=[{'AttributeName': n, 'AttributeType': 'S'} for n in names], GlobalSecondaryIndexes=indexes, BillingMode='PAY_PER_REQUEST')
        sqs = boto3.client('sqs', region_name='us-east-1')
        queue = sqs.create_queue(QueueName='jobs')['QueueUrl']
        clock = [1780315200]
        store = Store(table, boto3.client('dynamodb', region_name='us-east-1'), sqs, queue, clock=lambda: clock[0])
        emr = Mock()
        emr.submit.return_value = 's-STEP123'
        emr.status.return_value = 'RUNNING'
        emr.find.return_value = ([], '')
        emr.cancel.return_value = True
        service = Service(store, emr, copy.deepcopy(profiles), 'hadoop-dev')
        yield SimpleNamespace(store=store, service=service, emr=emr, clock=clock, table=table, sqs=sqs)


def event(method='POST', resource='/jobs', value=None, caller=CALLER, **kwargs):
    return {'httpMethod': method, 'resource': resource, 'headers': {'Idempotency-Key': 'valid-key-123'},
            'requestContext': {'identity': {'userArn': caller}}, 'body': json.dumps(value), **kwargs}
