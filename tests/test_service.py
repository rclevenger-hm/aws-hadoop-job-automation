import pytest
from app.validation import ApiError, digest
from conftest import CALLER, OTHER
from test_store import create


def message(job):
    return {'tenant': job['pk'], 'job_id': job['job_id']}


def test_duplicate_deliveries_submit_once(env, payload):
    job = create(env, payload)
    env.service.process(message(job))
    env.service.process(message(job))
    env.emr.submit.assert_called_once()
    assert env.store.get(job['pk'], job['job_id'])['step_id'] == 's-STEP123'


def test_timeout_after_start_becomes_unknown_never_resubmits(env, payload):
    job = create(env, payload)
    env.emr.submit.side_effect = TimeoutError('sensitive detail')
    env.service.process(message(job))
    env.service.process(message(job))
    current = env.store.get(job['pk'], job['job_id'])
    assert current['status'] == 'SUBMISSION_UNKNOWN'
    assert current['reason'] == 'SUBMISSION_OUTCOME_UNKNOWN'
    env.emr.submit.assert_called_once()
