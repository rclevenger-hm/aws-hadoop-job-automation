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

## Idempotency and status

Supply `Idempotency-Key` with 8–128 letters, digits, dots, underscores, colons or hyphens. Same caller/key/normalized payload returns the existing job; changed inputs return 409. The key is honored while metadata remains retained. An expired record pending TTL removal returns `EXPIRED_KEY`; use a fresh key only for a genuinely intended new execution.

Statuses: `QUEUED`, `SUBMITTING`, `SUBMISSION_UNKNOWN`, `SUBMITTED`, `RUNNING`, `CANCEL_REQUESTED`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `NEEDS_REVIEW`. `NEEDS_REVIEW` is a control-plane stop, not proof that remote work stopped. Do not change keys just because a submit call or status poll timed out.

Cancellation returns 200 for work cancelled before dispatch or already cancelled, and 202 when intent is pending. Remote cancellation acknowledgment is not completion. Completed jobs return 409 if a new cancellation is requested. A repeated cancellation request is safe.

## Pagination, logs and errors

History page limits are 1–100; cursor tokens bind the caller and status filter. Tokens are not authentication credentials. GSI consistency and filtering can yield empty pages with a next cursor; continue until it is null. Results are ordered newest first within the history index.

Logs allow `stdout`, `stderr` or `controller`. The response defaults to the first 16 KiB, with a maximum requested size of 64 KiB. Compressed reads and decompression are capped near 1 MiB to bound resource use; truncation is explicit. Invalid UTF-8 is replaced during display. `LOG_NOT_READY` means S3 archival is not available yet. No raw log data is copied into application logs.

Application errors contain `code`, `error`, and `request_id`; platform IAM errors may use a different envelope. 429 returns `Retry-After`. Daily admissions reset at 00:00 UTC; request windows reset each UTC minute. Poll with backoff and inspect `/usage` before retrying a daily allowance error.
