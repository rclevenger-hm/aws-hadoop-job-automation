# Security boundaries

## Caller and tenant identity

Every API Gateway route requires IAM. The resource policy explicitly denies principals outside configured profile callers. The application hashes a canonical IAM identity; assumed-role session names collapse to the same role tenant. Consumer ARNs with IAM paths are deliberately unsupported to avoid ambiguous STS role-name normalization. Separate service roles represent separate tenants.

Profile authorization occurs at admission. Ownership is checked on status, cancellation and log reads. Configuration is snapshotted with each accepted job so later profile edits cannot silently redirect that job to a different cluster or log bucket. To revoke pending work, cancel its queued jobs or pause intake/workers and follow the incident procedure; merely editing a profile does not rewrite accepted jobs.

## Execution boundary

Only the worker Lambda can call `AddJobFlowSteps`; its IAM policy restricts cluster ARNs and requires the runtime-role parameter to be absent. Only the reconciler can describe/list/cancel steps. The API reads only configured cluster step-log prefixes. No Lambda can launch or terminate clusters through these policies.

The API can also list at most one key per request under each configured cluster's step-log prefix. This narrowly scoped `s3:ListBucket` permission distinguishes a missing log from an unreadable object: S3 can return `AccessDenied` for a missing `GetObject` when bucket listing is restricted. An explicit exact-prefix lookup permits plaintext fallback or `LOG_NOT_READY` only when that candidate is absent. An existing inaccessible object, a failed list request, or a KMS denial remains a service error. The API never returns listing results or accepts a caller-supplied bucket/key. A compromised API role could enumerate names within these already-readable log prefixes; it cannot list the whole bucket with this policy.

JAR arguments are passed as an API array, not interpolated into a shell command. Nevertheless, a Hadoop JAR is executable code and inherits the existing cluster's privileges. Approved prefixes are not a code sandbox, and a JAR may ignore its nominal input/output arguments. Protect artifact publishing, restrict the cluster instance profile, and isolate mutually untrusted workloads using separate infrastructure.

## Data and recovery

Queues are encrypted with SQS-managed encryption; DynamoDB encryption, PITR and deletion protection are enabled. Metadata contains job paths/configuration, never AWS credentials or SSH private keys. Application logs record safe status/error categories and IDs; requested archived logs are returned only to their owner and may themselves contain sensitive application output.

A runtime identity can read the whole application table; tenant isolation is an application boundary, not per-tenant DynamoDB IAM enforcement. A compromised administrator can also alter job metadata or add misleading EMR step names. Review CloudTrail and guard operational access. Metadata restoration must not blindly replay historical queued records.

## Dependency maintenance

Production and development requirements are pinned with artifact hashes. CI audits the production dependency lock, checks code and configuration, runs behavior tests and validates infrastructure. Regenerate locks with `pip-compile --generate-hashes --allow-unsafe --strip-extras requirements.in` and the corresponding development input after reviewing updates. Here `--allow-unsafe` is pip-tools terminology for pinning installer/build packages, not disabling hash verification.
