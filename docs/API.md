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

## Request validation

Use [examples/job.json](../examples/job.json). Required fields are `profile`, `jar_path`, `job_class`, `input_path`, `output_path`. An optional `arguments` array contains at most 20 additional strings of 1,024 characters each. Unknown fields, null/non-object bodies, control characters and malformed Unicode are rejected. Body size is at most 64 KiB; each primary string is at most 4,096 characters; combined HadoopJarStep strings are at most 10,240 characters.

Profile configuration selects the cluster, approved S3 JAR prefixes, S3/HDFS input/output prefixes and allowed IAM callers. Percent escapes, dot-segment traversal, query strings and fragments are rejected in paths. These are input restrictions, not an execution sandbox: trusted JAR code can access whatever the cluster instance profile permits.

