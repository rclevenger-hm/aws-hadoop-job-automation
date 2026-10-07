# Validation evidence and acceptance

## Automated coverage

Tests cover the OCI-compatible fields, profile authorization, malformed bodies, UTF-8, URI traversal, aggregate EMR limits, structured argument construction, caller identity normalization, quota/idempotency transactions, concurrent claims, stale updates, pagination, expiry, queue recovery, ambiguous submission, paginated step discovery, cancellation races, terminal-state mapping, bounded gzip/plaintext logs, error redaction and partial SQS failures.

Moto exercises DynamoDB transactions, conditional writes, indexes and SQS operations in process. Botocore Stubber checks native EMR request shapes. These tools are useful contracts, not proof of live AWS IAM or EMR behavior. CI also verifies a production-only vendored artifact imports and runs three mocked Terraform plans for secure defaults and invalid configuration rejection.

## Live smoke test

After a reviewed deployment, choose a small trusted JAR, supported traditional EMR cluster and fresh output prefix. Run with an authorized consumer:

```sh
export RUN_BILLABLE_EMR_SMOKE=yes
export SMOKE_JOB_FILE=/absolute/path/to/approved-small-job.json
python scripts/smoke.py
```

The test submits once, repeats the same idempotency key and polls up to 15 minutes for success. It uses real cloud resources and executes your JAR; it does not launch a cluster. If it times out, inspect the original job rather than retrying under a new key.

## Production acceptance

Verify unsigned/disallowed callers fail and another allowed caller cannot read or cancel the job. Check the actual EMR arguments, input/output permissions and archived logs. Test cancellation with a harmless long-running job and verify its YARN outcome. Simulate a publish outage and confirm recovery. Exercise a lost submission response in a disposable environment and verify no second step is submitted. Verify DLQ alarms, uncertainty notifications, KMS access, TTL behavior and a controlled PITR restore.

Check these against your actual EMR release and application. Passing tests alone does not establish production readiness, exactly-once execution or full workload isolation.
