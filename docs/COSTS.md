# Cost and capacity

## Resource use

This stack provisions a serverless control plane around an existing EMR cluster. It does not reduce or cap the cluster's EC2/EMR charges. Step execution, S3 reads/writes, KMS, Lambda, API Gateway, DynamoDB indexes/PITR, SQS, logs, alarms and EventBridge can incur charges. A long-running or expensive JAR can spend far more than a small control-plane request suggests.

The default allowance is 100 accepted jobs per caller per UTC day and 60 API requests per caller per minute. The daily reservation is atomic with job creation; rejected duplicate-key conflicts do not charge another admission. It is a job-count allowance, not a spend meter. Accepted cancelled/failed jobs still consume an admission. Separate keys intentionally permit separate executions of identical content.

## Limits and budgets

Reserved concurrency defaults to API 10, worker 2 and reconciler 1; SQS event-source concurrency is 2. Gateway throttles at 20 requests/second with a burst of 40. Application validation caps each request and log response. EMR has its own release-specific active-step/history limits; cluster capacity and step concurrency remain operator-managed.

Terraform configures an account-wide USD monthly budget, notifying at 80% actual and 100% forecast. It includes unrelated account spending and is deliberately not presented as exact per-service attribution. Budgets notify; they do not halt jobs or enforce a hard spending limit. Use dedicated accounts or appropriate cost-allocation controls for clearer attribution, and review current [EMR pricing](https://aws.amazon.com/emr/pricing/) before live tests.
