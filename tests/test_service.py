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


def test_crashed_submitter_reconciles_by_exact_name(env, payload):
    job = create(env, payload)
    env.store.replace(job, status='SUBMITTING', submitted_at=env.clock[0])
    env.clock[0] += 121
    env.emr.find.return_value = (['s-FOUND'], '')
    env.service.reconcile_one(job['pk'], job['job_id'])
    assert env.store.get(job['pk'], job['job_id'])['step_id'] == 's-FOUND'
    env.emr.submit.assert_not_called()


def test_missing_remote_step_requires_review_without_retry(env, payload):
    job = create(env, payload)
    env.store.replace(job, status='SUBMISSION_UNKNOWN', submitted_at=env.clock[0])
    env.clock[0] += 86401
    env.service.reconcile_one(job['pk'], job['job_id'])
    assert env.store.get(job['pk'], job['job_id'])['status'] == 'NEEDS_REVIEW'
    env.emr.submit.assert_not_called()


def test_reconciliation_persists_page_and_matches(env, payload):
    job = create(env, payload)
    env.store.replace(job, status='SUBMITTING', submitted_at=env.clock[0])
    env.clock[0] += 121
    env.emr.find.return_value = (['s-FIRST'], 'next')
    env.service.reconcile_one(job['pk'], job['job_id'])
    first = env.store.get(job['pk'], job['job_id'])
    assert first['scan_marker'] == 'next' and 'step_id' not in first
    env.clock[0] += 31
    env.emr.find.return_value = (['s-FIRST'], '')
    env.service.reconcile_one(job['pk'], job['job_id'])
    assert env.store.get(job['pk'], job['job_id'])['step_id'] == 's-FIRST'


def test_multiple_correlation_matches_require_review(env, payload):
    job = create(env, payload)
    env.store.replace(job, status='SUBMITTING', submitted_at=env.clock[0])
    env.clock[0] += 121
    env.emr.find.return_value = (['s-FIRST', 's-SECOND'], '')
    env.service.reconcile_one(job['pk'], job['job_id'])
    assert env.store.get(job['pk'], job['job_id'])['reason'] == 'MULTIPLE_MATCHING_STEPS'
