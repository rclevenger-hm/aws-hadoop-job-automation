"""Explicitly opt-in: runs the operator-supplied JAR on an existing EMR cluster."""
import json
import os
import pathlib
import time
import uuid
from client import request

if os.environ.get('RUN_BILLABLE_EMR_SMOKE') != 'yes':
    raise SystemExit('Set RUN_BILLABLE_EMR_SMOKE=yes and SMOKE_JOB_FILE to an approved small job; this executes code and incurs AWS costs.')
job = json.loads(pathlib.Path(os.environ['SMOKE_JOB_FILE']).read_text())
key = str(uuid.uuid4())
first = request('POST', '/jobs', job, key)
second = request('POST', '/jobs', job, key)
assert first['job_id'] == second['job_id']
end = time.monotonic() + 900
while time.monotonic() < end:
    result = request('GET', f"/jobs/{first['job_id']}")
    if result['status'] in {'SUCCEEDED', 'FAILED', 'CANCELLED', 'NEEDS_REVIEW'}:
        assert result['status'] == 'SUCCEEDED', result['status']
        print(json.dumps(result, indent=2))
        break
    time.sleep(15)
else:
    raise SystemExit('Job did not finish within 15 minutes; inspect its existing ID before any resubmission.')
