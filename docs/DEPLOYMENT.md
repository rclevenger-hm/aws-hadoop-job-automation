# Deployment

## Existing cluster prerequisites

Use a traditional EMR-on-EC2 cluster in the same AWS account/region as this control plane. Install Hadoop and your JAR's dependencies, enable S3 step-log archival, and verify a small JAR through the EMR steps API first. Use a supported EMR release and test running-step cancellation (introduced in EMR 5.28). Maintain encrypted storage/networking and private network placement according to your cluster policy.

Generic Hadoop JAR steps run with the cluster's instance-profile privileges. This stack does not use `ExecutionRoleArn`: AWS documents that mode for Spark/Hive runtime-role jobs, not general MapReduce JAR parity. Do not target an application-scoped-runtime-role cluster with this configuration. Scope the existing instance profile to required input/output/JAR/log locations. Separate clusters/roles are required when workload-level tenant isolation is necessary.

JAR prefixes should be writable only by a reviewed artifact release process. Configure canonical directory prefixes ending in `/`; include no credentials, wildcards or traversal. Configure `log_uri` to exactly match the existing cluster's S3 log base directory. If logs use customer KMS keys, add them to `log_kms_key_arns` and authorize the API role in their key policies. No cluster or data bucket is created or modified by this stack.

## State and deployment identity

Create a private, encrypted, versioned S3 bucket for Terraform state separately. Terraform 1.10+ uses native `.tflock` objects, so the deployment role needs state read/write and lock read/write/delete permissions. Use a unique key per environment. The backend bucket remains outside this service stack.

Create GitHub OIDC trust for the exact repository and protected environment subject, with audience `sts.amazonaws.com`. The deployment role needs scoped management permissions for IAM runtime roles/policies, Lambda, API Gateway, DynamoDB, SQS, EventBridge, CloudWatch Logs/alarms, SNS and Budgets, plus `iam:PassRole` for the Lambda runtime roles and state-bucket access. These are provisioning permissions; consumer callers only need API invocation. Restrict OIDC trust so arbitrary forks and untrusted repositories cannot assume it.

