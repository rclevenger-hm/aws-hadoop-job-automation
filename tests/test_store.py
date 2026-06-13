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
