# Security boundaries

## Caller and tenant identity

Every API Gateway route requires IAM. The resource policy explicitly denies principals outside configured profile callers. The application hashes a canonical IAM identity; assumed-role session names collapse to the same role tenant. Consumer ARNs with IAM paths are deliberately unsupported to avoid ambiguous STS role-name normalization. Separate service roles represent separate tenants.

Profile authorization occurs at admission. Ownership is checked on status, cancellation and log reads. Configuration is snapshotted with each accepted job so later profile edits cannot silently redirect that job to a different cluster or log bucket. To revoke pending work, cancel its queued jobs or pause intake/workers and follow the incident procedure; merely editing a profile does not rewrite accepted jobs.

