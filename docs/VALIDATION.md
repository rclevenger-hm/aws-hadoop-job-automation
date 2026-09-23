# Validation evidence and acceptance

## Automated coverage

Tests cover the OCI-compatible fields, profile authorization, malformed bodies, UTF-8, URI traversal, aggregate EMR limits, structured argument construction, caller identity normalization, quota/idempotency transactions, concurrent claims, stale updates, pagination, expiry, queue recovery, ambiguous submission, paginated step discovery, cancellation races, terminal-state mapping, bounded gzip/plaintext logs, error redaction and partial SQS failures.

Moto exercises DynamoDB transactions, conditional writes, indexes and SQS operations in process. Botocore Stubber checks native EMR request shapes. These tools are useful contracts, not proof of live AWS IAM or EMR behavior. CI also verifies a production-only vendored artifact imports and runs three mocked Terraform plans for secure defaults and invalid configuration rejection.

