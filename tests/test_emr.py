import gzip
import io
from unittest.mock import Mock

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber
from app.emr import Emr, MAX_LOG
from app.validation import ApiError
from test_store import create


def test_structured_hadoop_step_uses_cluster_instance_profile(env, payload):
    payload['arguments'] = ['space here', '$(not-a-shell)']
    job = create(env, payload)
    client = boto3.client('emr', region_name='us-east-1')
    expected = {'JobFlowId': 'j-EXAMPLE123', 'Steps': [{'Name': job['step_name'], 'ActionOnFailure': 'CONTINUE', 'HadoopJarStep': {'Jar': payload['jar_path'], 'MainClass': payload['job_class'], 'Args': [payload['input_path'], payload['output_path'], *payload['arguments']]}}]}
    with Stubber(client) as stub:
        stub.add_response('add_job_flow_steps', {'StepIds': ['s-NATIVE']}, expected)
        assert Emr(client, None).submit(job) == 's-NATIVE'
        stub.assert_no_pending_responses()


def test_paginated_reconciliation_uses_exact_correlation_name(env, payload):
    job = create(env, payload)
    job.update(scan_marker='next', scan_matches=['s-OLD'])
    client = Mock()
    client.list_steps.return_value = {'Steps': [{'Name': job['step_name'], 'Id': 's-FOUND'}, {'Name': job['step_name'] + '-other', 'Id': 's-NO'}], 'Marker': 'again'}
    matches, marker = Emr(client, None).find(job)
    assert matches == ['s-FOUND', 's-OLD'] and marker == 'again'
    client.list_steps.assert_called_once_with(ClusterId='j-EXAMPLE123', Marker='next')


@pytest.mark.parametrize('remote,local', [('PENDING','SUBMITTED'),('RUNNING','RUNNING'),('COMPLETED','SUCCEEDED'),('FAILED','FAILED'),('INTERRUPTED','FAILED'),('CANCEL_PENDING','CANCEL_REQUESTED'),('CANCELLED','CANCELLED')])
def test_remote_states(env, payload, remote, local):
    job = create(env, payload)
    job['step_id'] = 's-STEP'
    client = Mock()
    client.describe_step.return_value = {'Step': {'Status': {'State': remote}}}
    assert Emr(client, None).status(job) == local


def test_log_is_owned_before_any_s3_access(env, payload):
    job = create(env, payload)
    with pytest.raises(ApiError):
        env.service.owned('arn:aws:iam::123456789012:role/Other', job['job_id'])
    env.emr.logs.assert_not_called()


def test_log_gzip_read_and_decompression_are_bounded(env, payload):
    job = create(env, payload)
    job['step_id'] = 's-STEP'
    s3 = Mock()
    raw = gzip.compress(b'a' * (MAX_LOG * 8))
    stream = StreamingBody(io.BytesIO(raw), len(raw))
    s3.get_object.return_value = {'Body': stream}
    result = Emr(None, s3).logs(job, 'stdout', 1024)
    assert result['text'] == 'a' * 1024 and result['truncated']
    assert s3.get_object.call_args.kwargs['Range'] == f'bytes=0-{MAX_LOG}'
    assert s3.get_object.call_args.kwargs['Key'] == 'clusters/j-EXAMPLE123/steps/s-STEP/stdout.gz'
    assert stream._raw_stream.closed


def test_log_missing_is_explicit_not_job_failure(env, payload):
    job = create(env, payload)
    job['step_id'] = 's-STEP'
    s3 = boto3.client('s3', region_name='us-east-1')
    with Stubber(s3) as stub:
        stub.add_client_error('get_object', service_error_code='NoSuchKey')
        stub.add_client_error('get_object', service_error_code='NoSuchKey')
        with pytest.raises(ApiError) as error:
            Emr(None, s3).logs(job, 'stderr', 1024)
        assert error.value.code == 'LOG_NOT_READY'


def test_log_plaintext_fallback(env, payload):
    from botocore.exceptions import ClientError
    job = create(env, payload)
    job['step_id'] = 's-STEP'
    s3 = Mock()
    s3.get_object.side_effect = [ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject'), {'Body': StreamingBody(io.BytesIO(b'hello'), 5)}]
    assert Emr(None, s3).logs(job, 'stdout', 1024)['text'] == 'hello'


def test_invalid_log_stream_cannot_select_other_keys(env, payload):
    job = create(env, payload)
    job['step_id'] = 's-STEP'
    with pytest.raises(ApiError):
        Emr(None, Mock()).logs(job, '../../other', 1024)


def test_malformed_step_response_is_ambiguous(env, payload):
    job = create(env, payload)
    client = Mock()
    client.add_job_flow_steps.return_value = {'StepIds': []}
    with pytest.raises(RuntimeError, match='ambiguous'):
        Emr(client, None).submit(job)


def log_request(job, suffix=''):
    return {'Bucket': 'your-emr-logs', 'Key': f"clusters/j-EXAMPLE123/steps/{job['step_id']}/stdout{suffix}", 'Range': f'bytes=0-{MAX_LOG}'}


def missing_lookup(request):
    return {'Bucket': request['Bucket'], 'Prefix': request['Key'], 'MaxKeys': 1}


@pytest.mark.parametrize('error_code', ['AccessDenied', '403'])
def test_missing_gzip_with_restricted_listing_falls_back_to_plaintext(env, payload, error_code):
    job = create(env, payload)
    job['step_id'] = 's-STEP'
    s3 = boto3.client('s3', region_name='us-east-1')
    compressed, plain = log_request(job, '.gz'), log_request(job)
    with Stubber(s3) as stub:
        stub.add_client_error('get_object', service_error_code=error_code, http_status_code=403, expected_params=compressed)
        stub.add_response('list_objects_v2', {'KeyCount': 0, 'IsTruncated': False}, missing_lookup(compressed))
        stub.add_response('get_object', {'Body': StreamingBody(io.BytesIO(b'plain log'), 9)}, plain)
        result = Emr(None, s3).logs(job, 'stdout', 1024)
        assert result['text'] == 'plain log' and not result['truncated']
        stub.assert_no_pending_responses()


def test_both_log_formats_absent_with_restricted_listing_are_not_ready(env, payload):
    job = create(env, payload)
    job['step_id'] = 's-STEP'
    s3 = boto3.client('s3', region_name='us-east-1')
    with Stubber(s3) as stub:
        for suffix in ['.gz', '']:
            request = log_request(job, suffix)
            stub.add_client_error('get_object', service_error_code='AccessDenied', http_status_code=403, expected_params=request)
            # Prefix matches are not exact object matches.
            stub.add_response('list_objects_v2', {'KeyCount': 1, 'Contents': [{'Key': request['Key'] + '.old'}]}, missing_lookup(request))
        with pytest.raises(ApiError) as error:
            Emr(None, s3).logs(job, 'stdout', 1024)
        assert error.value.code == 'LOG_NOT_READY'
        stub.assert_no_pending_responses()


@pytest.mark.parametrize('suffix', ['.gz', ''])
def test_existing_inaccessible_log_preserves_permission_error(env, payload, suffix):
    from botocore.exceptions import ClientError
    job = create(env, payload)
    job['step_id'] = 's-STEP'
    s3 = boto3.client('s3', region_name='us-east-1')
    request = log_request(job, suffix)
    with Stubber(s3) as stub:
        if not suffix:
            stub.add_client_error('get_object', service_error_code='NoSuchKey', expected_params=log_request(job, '.gz'))
        stub.add_client_error('get_object', service_error_code='AccessDenied', http_status_code=403, expected_params=request)
        stub.add_response('list_objects_v2', {'KeyCount': 1, 'Contents': [{'Key': request['Key']}]}, missing_lookup(request))
        with pytest.raises(ClientError) as error:
            Emr(None, s3).logs(job, 'stdout', 1024)
        assert error.value.response['Error']['Code'] == 'AccessDenied'
        assert error.value.operation_name == 'GetObject'
        stub.assert_no_pending_responses()


@pytest.mark.parametrize('error_code', ['AccessDenied', 'NoSuchBucket', 'SlowDown'])
def test_failed_absence_lookup_remains_a_service_error(env, payload, error_code):
    from botocore.exceptions import ClientError
    job = create(env, payload)
    job['step_id'] = 's-STEP'
    s3 = boto3.client('s3', region_name='us-east-1')
    request = log_request(job, '.gz')
    with Stubber(s3) as stub:
        stub.add_client_error('get_object', service_error_code='AccessDenied', http_status_code=403, expected_params=request)
        stub.add_client_error('list_objects_v2', service_error_code=error_code, expected_params=missing_lookup(request))
        with pytest.raises(ClientError) as error:
            Emr(None, s3).logs(job, 'stdout', 1024)
        assert error.value.operation_name == 'ListObjectsV2'
        stub.assert_no_pending_responses()


def test_missing_log_lookup_does_not_mask_unrelated_get_failures(env, payload):
    from botocore.exceptions import ClientError
    job = create(env, payload)
    job['step_id'] = 's-STEP'
    s3 = boto3.client('s3', region_name='us-east-1')
    with Stubber(s3) as stub:
        stub.add_client_error('get_object', service_error_code='SlowDown', expected_params=log_request(job, '.gz'))
        with pytest.raises(ClientError) as error:
            Emr(None, s3).logs(job, 'stdout', 1024)
        assert error.value.response['Error']['Code'] == 'SlowDown'
        stub.assert_no_pending_responses()
