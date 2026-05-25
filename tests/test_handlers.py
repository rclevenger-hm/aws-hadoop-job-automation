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
