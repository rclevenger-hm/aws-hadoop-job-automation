# API and client contract

Sign requests with AWS Signature Version 4 for service `execute-api` in the deployment region. `scripts/client.py` uses the normal boto3 credential chain, including SSO profiles and workload roles, and refuses redirects to avoid forwarding signed requests elsewhere. API Gateway verifies the signature; application code only trusts its verified request context.

