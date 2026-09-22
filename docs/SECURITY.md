# Security boundaries

## Caller and tenant identity

Every API Gateway route requires IAM. The resource policy explicitly denies principals outside configured profile callers. The application hashes a canonical IAM identity; assumed-role session names collapse to the same role tenant. Consumer ARNs with IAM paths are deliberately unsupported to avoid ambiguous STS role-name normalization. Separate service roles represent separate tenants.

Profile authorization occurs at admission. Ownership is checked on status, cancellation and log reads. Configuration is snapshotted with each accepted job so later profile edits cannot silently redirect that job to a different cluster or log bucket. To revoke pending work, cancel its queued jobs or pause intake/workers and follow the incident procedure; merely editing a profile does not rewrite accepted jobs.

## Execution boundary

Only the worker Lambda can call `AddJobFlowSteps`; its IAM policy restricts cluster ARNs and requires the runtime-role parameter to be absent. Only the reconciler can describe/list/cancel steps. The API reads only configured cluster step-log prefixes. No Lambda can launch or terminate clusters through these policies.

JAR arguments are passed as an API array, not interpolated into a shell command. Nevertheless, a Hadoop JAR is executable code and inherits the existing cluster's privileges. Approved prefixes are not a code sandbox, and a JAR may ignore its nominal input/output arguments. Protect artifact publishing, restrict the cluster instance profile, and isolate mutually untrusted workloads using separate infrastructure.

