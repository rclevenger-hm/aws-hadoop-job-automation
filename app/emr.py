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

    def cancel(self, job):
        result = self.client.cancel_steps(ClusterId=job['profile']['cluster_id'], StepIds=[job['step_id']], StepCancellationOption='SEND_INTERRUPT')
        entries = result.get('CancelStepsInfoList', [])
        return len(entries) == 1 and entries[0].get('StepId') == job['step_id'] and entries[0].get('Status') == 'SUBMITTED'

    def logs(self, job, stream, limit):
        if stream not in {'stdout', 'stderr', 'controller'}:
            raise ApiError(400, 'INVALID_STREAM', 'stream must be stdout, stderr or controller')
        if not job.get('step_id'):
            raise ApiError(409, 'NOT_SUBMITTED', 'No EMR step has been identified yet')
        p = job['profile']
        uri = urlsplit(p['log_uri'])
        key = f"{uri.path.lstrip('/')}{p['cluster_id']}/steps/{job['step_id']}/{stream}"
        for suffix in ['.gz', '']:
            try:
                response = self.s3.get_object(Bucket=uri.netloc, Key=key + suffix, Range=f'bytes=0-{MAX_LOG}')
                break
            except ClientError as exc:
                if exc.response['Error']['Code'] not in {'NoSuchKey', '404'}:
                    raise
        else:
            raise ApiError(404, 'LOG_NOT_READY', 'EMR has not archived this log yet')
        body = response['Body']
        try:
            raw = body.read(MAX_LOG + 1)
        finally:
            body.close()
        if suffix:
            decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
            try:
                data = decoder.decompress(raw[:MAX_LOG], MAX_LOG + 1)
            except zlib.error as exc:
                raise ApiError(502, 'INVALID_LOG', 'Archived log cannot be decoded') from exc
            truncated = not decoder.eof or bool(decoder.unused_data) or len(data) > limit
        else:
            data = raw
            truncated = len(data) > limit
        return {'stream': stream, 'text': data[:limit].decode('utf-8', errors='replace'), 'truncated': truncated,
                'limit_bytes': limit, 'note': 'Beginning of the archived log; uploads may lag execution.'}
