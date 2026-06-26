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


def test_unknown_request_fields_are_rejected(payload, profiles):
    payload['execution_role_arn'] = 'attacker'
    with pytest.raises(ApiError, match='Unknown'):
        job_request(payload, profiles, CALLER)


def test_aggregate_emr_limit(payload, profiles):
    payload['arguments'] = ['x' * 1024] * 10
    with pytest.raises(ApiError, match='10240'):
        job_request(payload, profiles, CALLER)


def test_base64_and_utf8_body():
    encoded = base64.b64encode(json.dumps({'text': '雪'}).encode()).decode()
    assert body({'body': encoded, 'isBase64Encoded': True}) == {'text': '雪'}


@pytest.mark.parametrize('raw', ['null', '[]', 'NaN', '{', '{"x":NaN}'])
def test_invalid_json_envelopes(raw):
    with pytest.raises(ApiError):
        body({'body': raw})


def test_body_size_and_invalid_base64():
    with pytest.raises(ApiError):
        body({'body': 'x' * 65537})
    with pytest.raises(ApiError):
        body({'body': '##', 'isBase64Encoded': True})


def test_assumed_role_sessions_share_identity():
    first = principal(event(caller='arn:aws:sts::123456789012:assumed-role/HadoopConsumer/first'))
    second = principal(event(caller='arn:aws:sts::123456789012:assumed-role/HadoopConsumer/second'))
    assert first == second == CALLER


def test_no_spoofed_identity_headers():
    with pytest.raises(ApiError):
        principal({'headers': {'userArn': CALLER}, 'requestContext': {'identity': {}}})


@pytest.mark.parametrize('value', ['-1', '0', '101', '1.2', 'NaN'])
def test_pagination_bounds(value):
    with pytest.raises(ApiError):
        integer(value, 20, 100)
