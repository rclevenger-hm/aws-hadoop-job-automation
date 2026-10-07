# Deployment

## Existing cluster prerequisites

Use a traditional EMR-on-EC2 cluster in the same AWS account/region as this control plane. Install Hadoop and your JAR's dependencies, enable S3 step-log archival, and verify a small JAR through the EMR steps API first. Use a supported EMR release and test running-step cancellation (introduced in EMR 5.28). Maintain encrypted storage/networking and private network placement according to your cluster policy.

Generic Hadoop JAR steps run with the cluster's instance-profile privileges. This stack does not use `ExecutionRoleArn`: AWS documents that mode for Spark/Hive runtime-role jobs, not general MapReduce JAR parity. Do not target an application-scoped-runtime-role cluster with this configuration. Scope the existing instance profile to required input/output/JAR/log locations. Separate clusters/roles are required when workload-level tenant isolation is necessary.

JAR prefixes should be writable only by a reviewed artifact release process. Configure canonical directory prefixes ending in `/`; include no credentials, wildcards or traversal. Configure `log_uri` to exactly match the existing cluster's S3 log base directory. If logs use customer KMS keys, add them to `log_kms_key_arns` and authorize the API role in their key policies. No cluster or data bucket is created or modified by this stack.

## State and deployment identity

Create a private, encrypted, versioned S3 bucket for Terraform state separately. Terraform 1.10+ uses native `.tflock` objects, so the deployment role needs state read/write and lock read/write/delete permissions. Use a unique key per environment. The backend bucket remains outside this service stack.

Create GitHub OIDC trust for the exact repository and protected environment subject, with audience `sts.amazonaws.com`. The deployment role needs scoped management permissions for IAM runtime roles/policies, Lambda, API Gateway, DynamoDB, SQS, EventBridge, CloudWatch Logs/alarms, SNS and Budgets, plus `iam:PassRole` for the Lambda runtime roles and state-bucket access. These are provisioning permissions; consumer callers only need API invocation. Restrict OIDC trust so arbitrary forks and untrusted repositories cannot assume it.

## Manual apply

```sh
python -m pip install --require-hashes -r requirements-dev.txt
python -m pytest
python scripts/build.py
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
cp terraform/backend.hcl.example terraform/backend.hcl
# Edit account, region, cluster, prefixes, consumers, state and email.
terraform -chdir=terraform init -backend-config=backend.hcl -lockfile=readonly
terraform -chdir=terraform plan -out=deploy.tfplan
terraform -chdir=terraform apply deploy.tfplan
terraform -chdir=terraform output
```

Lambda needs outbound access to AWS service APIs, not an SSH route into the cluster. Functions use the standard Lambda network configuration; the cluster can remain private. Provisioning IAM propagation may require retrying a failed first deployment after inspecting the error.

## GitHub deployment variables

Create a protected `dev`, `stage` or `prod` GitHub environment with:

| Variable | Purpose |
|---|---|
| `AWS_REGION` | Cluster/control-plane region |
| `AWS_DEPLOY_ROLE_ARN` | OIDC deployment role |
| `TF_STATE_BUCKET` | Pre-created state bucket |
| `CLUSTER_PROFILES` | JSON matching [profiles example](../examples/profiles.json) |
| `NOTIFICATION_EMAIL` | Operator email |
| `SERVICE_NAME` | Optional, default `hadoop` |
| `MONTHLY_BUDGET` | Optional account-wide USD budget, default 100 |
| `LOG_KMS_KEY_ARNS` | Optional JSON array, default `[]` |

Dispatch `Deploy AWS`. It verifies the source/artifact, assumes the deploy role, plans/applies Terraform, and checks unsigned requests fail. It never submits a billable Hadoop job automatically. Confirm the SNS email subscription after deployment. Grant consumers `execute-api:Invoke` on the `invoke_resource` output; both IAM identity and resource policies must permit cross-account access.

## Live acceptance and removal

Run the opt-in smoke test with an approved tiny JAR and unique output path. See [validation](VALIDATION.md). Verify a second caller cannot inspect the first caller's job. Monitor cost and uncertainty alarms during a pilot.

DynamoDB deletion protection is enabled. Decommission by stopping intake, resolving active/unknown jobs, retaining required history, and then explicitly reviewing deletion-protection removal. Destroying this control plane does not cancel EMR jobs or remove their outputs/logs.
