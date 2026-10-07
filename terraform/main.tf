terraform {
  required_version = ">= 1.10, < 2.0"
  backend "s3" { use_lockfile = true }
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}
provider "aws" {
  region = var.region
  default_tags { tags = local.tags }
}
data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
locals {
  prefix       = "${var.name}-${var.environment}"
  tags         = { Service = "hadoop-job-automation", Environment = var.environment, ManagedBy = "terraform" }
  consumers    = sort(distinct(flatten([for p in values(var.cluster_profiles) : p.allowed_principals])))
  cluster_arns = distinct([for p in values(var.cluster_profiles) : "arn:${data.aws_partition.current.partition}:elasticmapreduce:${var.region}:${data.aws_caller_identity.current.account_id}:cluster/${p.cluster_id}"])
  log_arns     = distinct([for p in values(var.cluster_profiles) : "arn:${data.aws_partition.current.partition}:s3:::${trimprefix(p.log_uri, "s3://")}${p.cluster_id}/steps/*"])
  env = {
    CLUSTER_PROFILES    = jsonencode(var.cluster_profiles)
    JOBS_TABLE          = aws_dynamodb_table.jobs.name
    JOBS_QUEUE_URL      = aws_sqs_queue.jobs.url
    SERVICE_NAME        = local.prefix
    DAILY_JOB_LIMIT     = tostring(var.daily_job_limit)
    REQUESTS_PER_MINUTE = tostring(var.requests_per_minute)
    RETENTION_DAYS      = tostring(var.retention_days)
  }
}
