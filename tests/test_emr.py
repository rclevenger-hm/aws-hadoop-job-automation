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
