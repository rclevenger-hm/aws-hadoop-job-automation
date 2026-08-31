# API and client contract

Sign requests with AWS Signature Version 4 for service `execute-api` in the deployment region. `scripts/client.py` uses the normal boto3 credential chain, including SSO profiles and workload roles, and refuses redirects to avoid forwarding signed requests elsewhere. API Gateway verifies the signature; application code only trusts its verified request context.

## Routes

| Method | Path | Result |
|---|---|---|
| POST | `/jobs` | 202 accepted, or 200 idempotent replay |
| GET | `/jobs` | Owned history with optional `status`, `limit`, `cursor` |
| GET | `/jobs/{job_id}` | Current persisted status and EMR step ID if known |
| POST | `/jobs/{job_id}/cancel` | Cancel queued job, or persist remote cancellation intent |
| GET | `/jobs/{job_id}/logs` | Bounded archived log; `stream`, `limit` |
| GET | `/usage` | Accepted jobs and daily limit for this UTC date |

