# OCI to AWS parity

Baseline: [oci-hadoop-job-automation](https://github.com/rclevenger-hm/oci-hadoop-job-automation) at `af9ac91b845aa1b8b709d1fdf74b58dc3cdeadde`, inspected in October 2026. The OCI implementation runs a validated command over SSH and waits up to 30 seconds after command acceptance; its asynchronous design is documentation rather than implemented behavior.

## Capability comparison

| Capability | OCI baseline | AWS implementation |
|---|---|---|
| Hadoop request | JAR, Java class, input, output | Same fields, plus profile and optional arguments |
| Remote execution | Shell-quoted SSH command | Structured EMR HadoopJarStep, no shell wrapper |
| Cluster trust | Pinned SSH host key | AWS SigV4/TLS, allowlisted EMR cluster IDs |
| Request limit | 64 KiB | Same; field and aggregate EMR limits |
| Completion | Short synchronous wait | Persistent asynchronous status and remote step ID |
| Output | Bounded stdout on success | Bounded archived stdout, stderr and controller endpoints |
| Idempotency | Not implemented | Caller-scoped key/fingerprint and atomic admission |
| Duplicate delivery | Not implemented | Conditional one-way submission claim |
| Ambiguous outcome | Warn caller not to blindly retry | Persist uncertainty, correlate exact step name, operator review |
| Status/history | Not implemented | Caller-owned status and cursor-paginated history |
| Cancellation | Not implemented | Safe queued cancellation and remote async cancellation |
| Recovery | Design only | Scheduled due-index polling and queue publish repair |
| Authorization | Runtime/SSH boundary | IAM gateway, explicit profile callers, tenant-owned records |
| Deployment | Normal OCI function workflow | Terraform, remote state, OIDC, locked artifact and CI |
| Monitoring | Operational guidance | Lambda/API/queue/DLQ/uncertainty alarms and account budget |

## Compatibility limits

AWS targets traditional EMR-on-EC2 clusters running Hadoop, not arbitrary EC2-hosted or OCI-hosted Hadoop installations. Local JAR paths must move to approved S3 prefixes. Input/output paths use configured S3 or HDFS directory URIs; add `profile` to the old request. JAR arguments remain positional input then output, followed by optional arguments. There is no SSH fallback.

Submission returns 202 with a stable ID rather than immediate stdout. Logs come from the cluster's configured S3 archive and can lag execution or be absent. The endpoint returns a bounded beginning of a log, not a complete output download or streaming tail. A successful step is determined by EMR's state, not by whether a log exists.

The application improves control-plane reliability; it cannot promise exactly-once EMR execution, enforce output-path exclusivity across different keys, isolate arbitrary untrusted JAR code, or prove a missing step never started. Those boundaries remain explicit.
