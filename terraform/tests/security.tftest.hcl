mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }
}
variables {
  notification_email = "operator@example.com"
  cluster_profiles = {
    analytics = {
      cluster_id         = "j-EXAMPLE123"
      allowed_principals = ["arn:aws:iam::123456789012:role/Consumer"]
      jar_prefixes       = ["s3://assets/approved/"]
      input_prefixes     = ["s3://data/input/"]
      output_prefixes    = ["s3://data/output/"]
      log_uri            = "s3://logs/clusters/"
    }
  }
}
run "secure_defaults" {
  command = plan
  assert {
    condition     = alltrue([for m in aws_api_gateway_method.route : m.authorization == "AWS_IAM"])
    error_message = "Every route must require IAM."
  }
  assert {
    condition     = aws_dynamodb_table.jobs.deletion_protection_enabled && aws_dynamodb_table.jobs.point_in_time_recovery[0].enabled
    error_message = "Persisted job history needs deletion protection and PITR."
  }
  assert {
    condition     = contains(aws_lambda_event_source_mapping.jobs.function_response_types, "ReportBatchItemFailures") && aws_sqs_queue.jobs.visibility_timeout_seconds >= 6 * aws_lambda_function.service["worker"].timeout
    error_message = "SQS needs partial batch reporting and enough visibility time."
  }
  assert {
    condition     = aws_sqs_queue.jobs.sqs_managed_sse_enabled && aws_sqs_queue.dead_letter.message_retention_seconds == 1209600
    error_message = "Encrypt queues and retain dead letters for investigation."
  }
  assert {
    condition     = alltrue([for statement in concat(local.runtime_statements["api"], local.runtime_statements["reconcile"]) : !contains(statement.Action, "elasticmapreduce:AddJobFlowSteps")])
    error_message = "Only the worker may submit EMR steps."
  }
}
run "reject_negative_quota" {
  command = plan
  variables { daily_job_limit = -1 }
  expect_failures = [var.daily_job_limit]
}
run "reject_public_consumer" {
  command = plan
  variables {
    cluster_profiles = {
      analytics = {
        cluster_id         = "j-EXAMPLE123"
        allowed_principals = ["*"]
        jar_prefixes       = ["s3://assets/approved/"]
        input_prefixes     = ["s3://data/input/"]
        output_prefixes    = ["s3://data/output/"]
        log_uri            = "s3://logs/clusters/"
      }
    }
  }
  expect_failures = [var.cluster_profiles]
}
run "log_lookup_is_prefix_scoped" {
  command = plan
  variables {
    cluster_profiles = {
      analytics = {
        cluster_id         = "j-EXAMPLE123"
        allowed_principals = ["arn:aws:iam::123456789012:role/Consumer"]
        jar_prefixes       = ["s3://assets/approved/"]
        input_prefixes     = ["s3://data/input/"]
        output_prefixes    = ["s3://data/output/"]
        log_uri            = "s3://logs/clusters/"
      }
      reporting = {
        cluster_id         = "j-OTHER456"
        allowed_principals = ["arn:aws:iam::123456789012:role/Consumer"]
        jar_prefixes       = ["s3://assets/approved/"]
        input_prefixes     = ["s3://data/input/"]
        output_prefixes    = ["s3://data/output/"]
        log_uri            = "s3://other-logs/archive/nested/"
      }
    }
  }
  assert {
    condition = toset([for s in local.runtime_statements["api"] : jsonencode({
      resource = s.Resource, condition = s.Condition
      }) if contains(s.Action, "s3:ListBucket")]) == toset([
      jsonencode({ resource = "arn:aws:s3:::logs", condition = {
        StringLike = { "s3:prefix" = "clusters/j-EXAMPLE123/steps/*" }, NumericLessThanEquals = { "s3:max-keys" = "1" }
      } }),
      jsonencode({ resource = "arn:aws:s3:::other-logs", condition = {
        StringLike = { "s3:prefix" = "archive/nested/j-OTHER456/steps/*" }, NumericLessThanEquals = { "s3:max-keys" = "1" }
      } })
    ])
    error_message = "Log absence checks must list at most one key under the matching bucket's cluster step-log prefix."
  }
  assert {
    condition     = alltrue([for s in concat(local.runtime_statements["worker"], local.runtime_statements["reconcile"]) : !contains(s.Action, "s3:ListBucket")])
    error_message = "Only the API role needs log absence checks."
  }
  assert {
    condition     = toset(local.log_arns) == toset(["arn:aws:s3:::logs/clusters/j-EXAMPLE123/steps/*", "arn:aws:s3:::other-logs/archive/nested/j-OTHER456/steps/*"])
    error_message = "Object-read scope must remain restricted to the corresponding cluster step logs."
  }
}
