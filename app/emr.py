import zlib
from urllib.parse import urlsplit

from botocore.exceptions import ClientError
from app.validation import ApiError

REMOTE_STATES = {'PENDING': 'SUBMITTED', 'CANCEL_PENDING': 'CANCEL_REQUESTED', 'RUNNING': 'RUNNING',
                 'COMPLETED': 'SUCCEEDED', 'CANCELLED': 'CANCELLED', 'FAILED': 'FAILED', 'INTERRUPTED': 'FAILED'}
MAX_LOG = 1024 * 1024


class Emr:
    def __init__(self, client, s3):
        self.client, self.s3 = client, s3

    def submit(self, job):
        r, p = job['request'], job['profile']
        response = self.client.add_job_flow_steps(JobFlowId=p['cluster_id'], Steps=[{
            'Name': job['step_name'], 'ActionOnFailure': 'CONTINUE',
            'HadoopJarStep': {'Jar': r['jar_path'], 'MainClass': r['job_class'], 'Args': [r['input_path'], r['output_path'], *r['arguments']]},
        }])
        ids = response.get('StepIds', [])
        if len(ids) != 1 or not isinstance(ids[0], str) or not ids[0].startswith('s-'):
            raise RuntimeError('EMR returned an ambiguous step identity')
        return ids[0]

    def find(self, job):
        args = {'ClusterId': job['profile']['cluster_id']}
        if job.get('scan_marker'):
            args['Marker'] = job['scan_marker']
        page = self.client.list_steps(**args)
        found = set(job.get('scan_matches', []))
        for step in page.get('Steps', []):
            if step.get('Name') == job['step_name']:
                found.add(step['Id'])
        return sorted(found), page.get('Marker', '')

    def status(self, job):
        response = self.client.describe_step(ClusterId=job['profile']['cluster_id'], StepId=job['step_id'])['Step']['Status']
        state = REMOTE_STATES.get(response['State'])
        if not state:
            raise RuntimeError('Unrecognized EMR state')
        return state
