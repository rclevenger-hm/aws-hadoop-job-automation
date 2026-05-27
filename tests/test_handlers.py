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


def test_unauthenticated_request_never_initializes_runtime(monkeypatch):
    factory = Mock(side_effect=AssertionError('must not initialize'))
    monkeypatch.setattr(handlers, 'runtime', factory)
    response = handlers.api_handler({}, CONTEXT)
    assert response['statusCode'] == 401
    factory.assert_not_called()


def test_internal_error_does_not_leak_payload(env, payload, monkeypatch, caplog):
    env.store.request_limit = Mock(side_effect=RuntimeError('secret-password'))
    response, result = api(env, monkeypatch, event(value=payload))
    assert response['statusCode'] == 503
    assert 'secret-password' not in response['body'] + caplog.text
    assert result['request_id'] == 'request-test'
