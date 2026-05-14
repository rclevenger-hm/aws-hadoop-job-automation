import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import boto3
import pytest
from moto import mock_aws

from app.config import load_profiles
from app.service import Service
from app.store import Store

CALLER = 'arn:aws:iam::123456789012:role/HadoopConsumer'
OTHER = 'arn:aws:iam::123456789012:role/OtherConsumer'


@pytest.fixture
def profiles():
    return load_profiles(open('examples/profiles.json').read())
