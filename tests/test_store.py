import base64
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.validation import ApiError, digest
from conftest import CALLER


def create(env, payload, key='job-key-001'):
    public, _ = env.service.submit(CALLER, key, payload)
    return env.store.get(digest(CALLER), public['job_id'])


def test_duplicate_submission_preserves_one_allowance(env, payload):
    first = create(env, payload)
    second = create(env, payload)
    assert first['job_id'] == second['job_id']
    assert env.store.usage(digest(CALLER))['jobs'] == 1


def test_changed_payload_key_conflicts(env, payload):
    create(env, payload)
    payload['arguments'] = ['new']
    with pytest.raises(ApiError) as error:
        create(env, payload)
    assert error.value.status == 409
    assert env.store.usage(digest(CALLER))['jobs'] == 1


def test_quota_and_job_creation_are_atomic(env, payload):
    env.store.daily_limit = 1
    first = create(env, payload)
    with pytest.raises(ApiError) as error:
        create(env, payload, 'job-key-002')
    assert error.value.status == 429
    assert len(env.store.history(digest(CALLER))[0]) == 1
    assert create(env, payload)['job_id'] == first['job_id']


def test_competing_claims_have_one_winner(env, payload):
    job = create(env, payload)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: env.store.replace(job, status='SUBMITTING'), range(2)))
    assert sum(r is not None for r in results) == 1


def test_stale_write_cannot_regress_state(env, payload):
    job = create(env, payload)
    latest = env.store.replace(job, status='RUNNING')
    assert env.store.replace(job, status='QUEUED') is None
    assert env.store.get(job['pk'], job['job_id'])['version'] == latest['version']
