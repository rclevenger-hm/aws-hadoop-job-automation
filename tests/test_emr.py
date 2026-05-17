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
