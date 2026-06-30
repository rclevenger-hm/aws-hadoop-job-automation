"""SigV4 API client. Credentials come only from the normal boto3 provider chain."""
import argparse
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request
import uuid

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(method, path, payload=None, key=None):
    endpoint = os.environ['API_ENDPOINT'].rstrip('/')
    if urllib.parse.urlsplit(endpoint).scheme != 'https':
        raise ValueError('API_ENDPOINT must use HTTPS')
    session = boto3.Session()
    credentials = session.get_credentials()
    if not credentials:
        raise ValueError('Configure AWS credentials or a workload role')
    headers = {'Content-Type': 'application/json', **({'Idempotency-Key': key} if key else {})}
    data = json.dumps(payload).encode() if payload is not None else None
    signed = AWSRequest(method=method, url=endpoint + path, data=data, headers=headers)
    SigV4Auth(credentials.get_frozen_credentials(), 'execute-api', os.environ.get('AWS_REGION') or session.region_name or 'us-east-1').add_auth(signed)
    prepared = urllib.request.Request(signed.url, data=data, headers=dict(signed.headers.items()), method=method)
    try:
        with urllib.request.build_opener(NoRedirect).open(prepared, timeout=35) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Do not echo response bodies, tokens, signed headers or submitted paths on failure.
        raise RuntimeError(f'API returned HTTP {exc.code}; request ID {exc.headers.get("X-Request-Id", "unknown")}') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['submit', 'status', 'list', 'cancel', 'logs', 'usage'])
    parser.add_argument('value', nargs='?')
    parser.add_argument('--key')
    parser.add_argument('--stream', choices=['stdout', 'stderr', 'controller'], default='stdout')
    parser.add_argument('--cursor')
    parser.add_argument('--status')
    args = parser.parse_args()
    if args.command == 'submit':
        if not args.value:
            parser.error('submit requires a JSON file')
        key = args.key or str(uuid.uuid4())
        print(f'Idempotency-Key: {key}', file=__import__('sys').stderr)
        result = request('POST', '/jobs', json.loads(pathlib.Path(args.value).read_text()), key)
    elif args.command in {'status', 'cancel', 'logs'}:
        if not args.value:
            parser.error(f'{args.command} requires a job ID')
        suffix = '/cancel' if args.command == 'cancel' else '/logs?' + urllib.parse.urlencode({'stream': args.stream}) if args.command == 'logs' else ''
        result = request('POST' if args.command == 'cancel' else 'GET', '/jobs/' + urllib.parse.quote(args.value, safe='') + suffix)
    else:
        query = urllib.parse.urlencode({k: v for k, v in {'cursor': args.cursor, 'status': args.status}.items() if v})
        result = request('GET', '/usage' if args.command == 'usage' else '/jobs' + ('?' + query if query else ''))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
