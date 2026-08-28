# AWS Hadoop Job Automation

[![CI](https://github.com/rclevenger-hm/aws-hadoop-job-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/rclevenger-hm/aws-hadoop-job-automation/actions/workflows/ci.yml)

Submit validated Hadoop JAR jobs to existing Amazon EMR clusters through an IAM-authenticated API. Lambda, SQS and DynamoDB provide durable intake, idempotency, background execution, status, cancellation and recovery. Terraform provisions the control plane; it does not launch or terminate EMR clusters.

