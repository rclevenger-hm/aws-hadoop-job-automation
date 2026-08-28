# AWS Hadoop Job Automation

[![CI](https://github.com/rclevenger-hm/aws-hadoop-job-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/rclevenger-hm/aws-hadoop-job-automation/actions/workflows/ci.yml)

Submit validated Hadoop JAR jobs to existing Amazon EMR clusters through an IAM-authenticated API. Lambda, SQS and DynamoDB provide durable intake, idempotency, background execution, status, cancellation and recovery. Terraform provisions the control plane; it does not launch or terminate EMR clusters.

## Capabilities

- Preserve the OCI request's JAR, Java class, input and output fields, with a server-configured cluster profile and optional argument vector.
- Return a stable job ID immediately; inspect status and history independently of function execution time.
- Reserve the daily allowance atomically with the job and enforce per-caller request limits.
- Fence concurrent workers and reconcile ambiguous EMR responses without blindly submitting another step.
- Cancel queued work locally; request asynchronous EMR cancellation once a step is known.
- Read bounded archived stdout/stderr/controller logs without SSH keys or arbitrary S3 access.
- Deploy with IAM roles, OIDC, persistent Terraform state, queue/DLQ alarms, uncertain-submission alerts, metadata PITR and a cost budget.

This implements the [OCI project's](https://github.com/rclevenger-hm/oci-hadoop-job-automation) proposed asynchronous control plane. See [parity and compatibility](docs/PARITY.md) for the different execution and output contracts.

