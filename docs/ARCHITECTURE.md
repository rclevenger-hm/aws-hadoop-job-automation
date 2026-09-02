# Architecture and state transitions

API Gateway requires AWS_IAM on every route and a resource-policy allowlist. The API Lambda derives the tenant from the verified IAM identity, validates the caller's cluster profile and request, then atomically creates a DynamoDB job and reserves one daily admission. It sends only tenant/job hashes to SQS. A failed queue publish leaves recoverable metadata rather than losing the request.

## Submission fence

The worker conditionally replaces `QUEUED` with `SUBMITTING` using a version number before calling EMR. Only that transition winner invokes `AddJobFlowSteps`, and the EMR client uses one total SDK attempt. The step name contains the service prefix and globally caller-scoped job hash. A returned step ID is attached without discarding a concurrent cancellation request.

A crash before the API call can leave a job that never ran. A timeout after acceptance can leave a job already running. Both states remain ambiguous; the service prioritizes avoiding duplicate execution over automatic resubmission. A duplicate SQS delivery cannot move a non-queued job back into submission.

## Reconciliation

EventBridge invokes the reconciler every minute. A 16-shard DynamoDB GSI orders nonterminal jobs by next-check time. Conditional updates move each claimed job's due time forward, preventing stale index reads or concurrent invocations from processing the same version. Shard start order rotates each minute; each query reads at most 25 jobs and the loop stops before Lambda's deadline.

Queued jobs are republished, but never directly submitted by the reconciler. A queued admission older than one day fails before execution. Unlinked submissions older than two minutes are searched through paginated `ListSteps` using an exact correlation name. Pagination markers and candidate IDs persist across runs. One match is attached only after completing the scan; multiple matches require review. No match after one day becomes `NEEDS_REVIEW`, which ends automatic tracking without asserting the remote job failed.

Known steps are described and mapped to submitted/running/succeeded/failed/cancelled. Cancellation remains requested until a later describe confirms a terminal state; success can win the race. `CancelSteps` uses `SEND_INTERRUPT`, so Hadoop/JAR shutdown behavior must be verified for your application.

## Retention and indexes

Active records have no TTL and remain recoverable. Terminal/control-plane-review records receive retention TTL (30 days by default); application reads deny them after that timestamp even before DynamoDB removes them. The history GSI is eventually consistent; returned rows are re-read from the base table so stale index state cannot regress a response. Status filtering may produce an empty page with a continuation cursor.

DynamoDB metadata and EMR steps/logs have independent retention. Restore metadata with PITR cautiously: a restored queued record could precede an already-submitted step. Pause submission and reconcile restored jobs against EMR before resuming.
