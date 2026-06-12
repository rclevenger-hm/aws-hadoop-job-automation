import base64
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.validation import ApiError, digest
from conftest import CALLER


def create(env, payload, key='job-key-001'):
    public, _ = env.service.submit(CALLER, key, payload)
    return env.store.get(digest(CALLER), public['job_id'])
