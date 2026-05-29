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


def test_partial_sqs_failure_reports_only_failed_message(env, payload, monkeypatch):
    monkeypatch.setattr(handlers, '_SERVICE', env.service)
    good, _ = env.service.submit(CALLER, 'example-key-123', payload)
    from app.validation import digest
    result = handlers.worker_handler({'Records': [
        {'messageId': 'good', 'body': json.dumps({'tenant': digest(CALLER), 'job_id': good['job_id']})},
        {'messageId': 'bad', 'body': '{'},
    ]}, CONTEXT)
    assert result == {'batchItemFailures': [{'itemIdentifier': 'bad'}]}
    env.emr.submit.assert_called_once()


def test_list_and_usage(env, payload, monkeypatch):
    api(env, monkeypatch, event(value=payload))
    _, listed = api(env, monkeypatch, event('GET', '/jobs'))
    _, usage = api(env, monkeypatch, event('GET', '/usage'))
    assert len(listed['jobs']) == 1 and usage['jobs'] == 1


def test_reconcile_failures_raise_for_lambda_alarm(env, monkeypatch):
    monkeypatch.setattr(handlers, '_SERVICE', env.service)
    env.service.reconcile = Mock(return_value={'failed': 1, 'processed': 2})
    with pytest.raises(RuntimeError):
        handlers.reconcile_handler({}, SimpleNamespace(get_remaining_time_in_millis=lambda: 100000))


def test_production_emr_client_disables_automatic_retries(env, monkeypatch, profiles):
    monkeypatch.setenv('CLUSTER_PROFILES', json.dumps(profiles))
    monkeypatch.setenv('JOBS_TABLE', 'jobs')
    monkeypatch.setenv('JOBS_QUEUE_URL', env.store.queue_url)
    monkeypatch.setenv('SERVICE_NAME', 'hadoop-dev')
    service = handlers.runtime()
    assert service.emr.client.meta.config.retries['total_max_attempts'] == 1
    assert service.emr.client.meta.config.read_timeout == 8
