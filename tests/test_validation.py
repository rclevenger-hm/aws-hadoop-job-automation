import base64
import json

import pytest
from app.config import load_profiles
from app.validation import ApiError, body, integer, job_request, principal
from conftest import CALLER, OTHER, event


def test_oci_four_fields_map_to_emr_with_profile(payload, profiles):
    assert job_request(payload, profiles, CALLER) == payload


@pytest.mark.parametrize('field,value', [('job_class', 'org.Job;rm'), ('job_class', 'bad class'), ('jar_path', 's3://elsewhere/job.jar'), ('input_path', 's3://your-data/input/../secret'), ('input_path', 's3://your-data/input/%2e%2e/x'), ('input_path', 's3://your-data/input/x\n'), ('output_path', 's3://your-data/outputx/file'), ('jar_path', None), ('arguments', 'x'), ('arguments', ['x'] * 21), ('arguments', ['x' * 1025]), ('job_class', '\ud800')])
def test_invalid_fields_fail_before_execution(payload, profiles, field, value):
    payload[field] = value
    with pytest.raises(ApiError):
        job_request(payload, profiles, CALLER)


def test_java_arguments_are_data_not_shell(payload, profiles):
    payload['arguments'] = ['$(touch /tmp/owned)', 'two words', 'a; b']
    assert job_request(payload, profiles, CALLER)['arguments'] == payload['arguments']


def test_profile_authorization(payload, profiles):
    with pytest.raises(ApiError, match='not authorized'):
        job_request(payload, profiles, OTHER)
