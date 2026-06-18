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


def test_terminal_ttl_and_active_index_removal(env, payload):
    job = create(env, payload)
    assert 'expires_at' not in job
    done = env.store.replace(job, status='SUCCEEDED')
    assert 'active_pk' not in done and 'active_sk' not in done
    assert done['expires_at'] == env.clock[0] + 30 * 86400
    env.clock[0] = done['expires_at']
    assert env.store.get(job['pk'], job['job_id']) is None


def test_expired_key_not_silently_reused_before_ttl(env, payload):
    job = create(env, payload)
    done = env.store.replace(job, status='SUCCEEDED')
    env.clock[0] = done['expires_at']
    with pytest.raises(ApiError) as error:
        create(env, payload)
    assert error.value.code == 'EXPIRED_KEY'


def test_rate_limit_atomic_and_resets(env):
    env.store.rate_limit = 2
    env.store.request_limit('caller')
    env.store.request_limit('caller')
    with pytest.raises(ApiError) as error:
        env.store.request_limit('caller')
    assert error.value.code == 'RATE_LIMIT'
    env.clock[0] += 60
    env.store.request_limit('caller')


def test_history_pagination_bound_to_caller_and_filter(env, payload):
    for i in range(3):
        create(env, payload, f'job-key-00{i}')
        env.clock[0] += 1
    first, cursor = env.store.history(digest(CALLER), limit=1)
    second, _ = env.store.history(digest(CALLER), limit=1, cursor=cursor)
    assert first[0]['job_id'] != second[0]['job_id']
    with pytest.raises(ApiError):
        env.store.history('another', cursor=cursor)
    with pytest.raises(ApiError):
        env.store.history(digest(CALLER), cursor=cursor, status='RUNNING')
    decoded = json.loads(base64.urlsafe_b64decode(cursor))
    decoded['key']['pk'] = 'another'
    with pytest.raises(ApiError):
        env.store.history(digest(CALLER), cursor=base64.urlsafe_b64encode(json.dumps(decoded).encode()).decode())


def test_empty_filtered_pages_keep_continuation(env, payload):
    create(env, payload, 'job-key-001')
    create(env, payload, 'job-key-002')
    jobs, cursor = env.store.history(digest(CALLER), limit=1, status='RUNNING')
    assert jobs == [] and cursor
