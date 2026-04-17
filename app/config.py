import json
import os
import re
from urllib.parse import urlsplit


def load_profiles(raw):
    profiles = json.loads(raw)
    if not isinstance(profiles, dict) or not 1 <= len(profiles) <= 5:
        raise ValueError('Configure one to five cluster profiles')
    for name, p in profiles.items():
        if not re.fullmatch(r'[a-z][a-z0-9-]{2,39}', name) or not isinstance(p, dict):
            raise ValueError('Invalid cluster profile')
        if not re.fullmatch(r'j-[A-Z0-9]+', p.get('cluster_id', '')):
            raise ValueError('Invalid EMR cluster ID')
        principals = p.get('allowed_principals', [])
        if not isinstance(principals, list) or not principals or any(not re.fullmatch(r'arn:aws(?:-us-gov|-cn)?:iam::\d{12}:(?:role|user)/[A-Za-z0-9+=,.@_-]+', a) for a in principals):
            raise ValueError('Use explicit IAM role/user ARNs without paths or session names')
        for field in ['jar_prefixes', 'input_prefixes', 'output_prefixes']:
            values = p.get(field, [])
            if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v.endswith('/') or '%' in v or '\\' in v or '*' in v or '?' in v or '#' in v or any(x in {'.', '..'} for x in urlsplit(v).path.split('/')) or urlsplit(v).scheme not in ({'s3'} if field == 'jar_prefixes' else {'s3', 'hdfs'}) or (urlsplit(v).scheme == 's3' and not urlsplit(v).netloc) for v in values):
                raise ValueError(f'Invalid {field}: use canonical directory URIs ending in /')
        log = urlsplit(p.get('log_uri', ''))
        if log.scheme != 's3' or not log.netloc or not p['log_uri'].endswith('/') or any(v in p['log_uri'] for v in ['*', '?', '#', '%', '\\']) or any(x in {'.', '..'} for x in log.path.split('/')):
            raise ValueError('Configure the existing cluster S3 log directory ending in /')
    return profiles
