# Cost and capacity

## Resource use

This stack provisions a serverless control plane around an existing EMR cluster. It does not reduce or cap the cluster's EC2/EMR charges. Step execution, S3 reads/writes, KMS, Lambda, API Gateway, DynamoDB indexes/PITR, SQS, logs, alarms and EventBridge can incur charges. A long-running or expensive JAR can spend far more than a small control-plane request suggests.

The default allowance is 100 accepted jobs per caller per UTC day and 60 API requests per caller per minute. The daily reservation is atomic with job creation; rejected duplicate-key conflicts do not charge another admission. It is a job-count allowance, not a spend meter. Accepted cancelled/failed jobs still consume an admission. Separate keys intentionally permit separate executions of identical content.

