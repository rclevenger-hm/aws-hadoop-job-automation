import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app import handlers
from conftest import CALLER, event

CONTEXT = SimpleNamespace(aws_request_id='request-test')


@pytest.fixture(autouse=True)
def reset_runtime(monkeypatch):
    monkeypatch.setattr(handlers, '_SERVICE', None)


def api(env, monkeypatch, request):
    monkeypatch.setattr(handlers, '_SERVICE', env.service)
    result = handlers.api_handler(request, CONTEXT)
    return result, json.loads(result['body'])


def test_submit_replay_and_status_api(env, payload, monkeypatch):
    response, first = api(env, monkeypatch, event(value=payload))
    assert response['statusCode'] == 202
    response, second = api(env, monkeypatch, event(value=payload))
    assert response['statusCode'] == 200 and first['job_id'] == second['job_id']
    response, status = api(env, monkeypatch, event('GET', '/jobs/{job_id}', pathParameters={'job_id': first['job_id']}))
    assert status['status'] == 'QUEUED' and 'request' not in status and 'profile' in status
