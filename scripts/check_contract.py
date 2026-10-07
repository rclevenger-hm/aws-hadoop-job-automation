"""Check documented routes, examples and YAML before publishing."""
import ast
import json
from pathlib import Path
import sys

import yaml
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import load_profiles
from app.validation import job_request

profiles = load_profiles(Path('examples/profiles.json').read_text())
payload = json.loads(Path('examples/job.json').read_text())
job_request(payload, profiles, profiles[payload['profile']]['allowed_principals'][0])
for path in [Path('openapi.yaml'), *Path('.github').rglob('*.yml')]:
    yaml.safe_load(path.read_text())
spec = yaml.safe_load(Path('openapi.yaml').read_text())
assert set(spec['paths']) == {'/jobs', '/jobs/{job_id}', '/jobs/{job_id}/cancel', '/jobs/{job_id}/logs', '/usage'}
for path in Path('app').glob('*.py'):
    ast.parse(path.read_text())
print('Examples, API routes and configuration syntax passed')
