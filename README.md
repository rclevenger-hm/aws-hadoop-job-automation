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

## Local verification

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.txt
ruff check app tests scripts
python -m pytest
python scripts/check_contract.py
pip-audit -r requirements.txt --disable-pip
python scripts/build.py
terraform -chdir=terraform init -backend=false -lockfile=readonly
terraform -chdir=terraform validate
terraform -chdir=terraform test
```

Use Python 3.12+ locally; Lambda/CI use Python 3.13. Tests use Moto and botocore stubs without AWS credentials, live EMR execution or cloud provisioning. The artifact vendors a hash-locked boto3 stack instead of depending on the runtime's bundled SDK.

## Deploy and call

Follow [deployment](docs/DEPLOYMENT.md). Configure an existing traditional EMR-on-EC2 cluster with Hadoop, S3 log archival, approved JARs and narrowly scoped instance-profile permissions. Per-step Spark/Hive runtime-role clusters are outside this Hadoop JAR implementation.

```sh
export API_ENDPOINT='https://API_ID.execute-api.us-east-1.amazonaws.com/v1'
export AWS_REGION='us-east-1'
export AWS_PROFILE='hadoop-consumer'
python scripts/client.py submit examples/job.json --key wordcount-run-001
python scripts/client.py list
python scripts/client.py status JOB_ID
python scripts/client.py logs JOB_ID --stream stdout
python scripts/client.py cancel JOB_ID
```

Replace example bucket/cluster names and use a fresh output directory for each intended run. A JAR executes with the cluster's workload privileges: only trusted, reviewed artifacts belong under approved prefixes.

