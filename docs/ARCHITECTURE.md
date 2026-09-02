# Architecture and state transitions

API Gateway requires AWS_IAM on every route and a resource-policy allowlist. The API Lambda derives the tenant from the verified IAM identity, validates the caller's cluster profile and request, then atomically creates a DynamoDB job and reserves one daily admission. It sends only tenant/job hashes to SQS. A failed queue publish leaves recoverable metadata rather than losing the request.

## Submission fence

The worker conditionally replaces `QUEUED` with `SUBMITTING` using a version number before calling EMR. Only that transition winner invokes `AddJobFlowSteps`, and the EMR client uses one total SDK attempt. The step name contains the service prefix and globally caller-scoped job hash. A returned step ID is attached without discarding a concurrent cancellation request.

A crash before the API call can leave a job that never ran. A timeout after acceptance can leave a job already running. Both states remain ambiguous; the service prioritizes avoiding duplicate execution over automatic resubmission. A duplicate SQS delivery cannot move a non-queued job back into submission.

