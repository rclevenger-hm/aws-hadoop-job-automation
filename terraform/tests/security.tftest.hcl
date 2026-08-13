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
    condition     = !strcontains(aws_iam_role_policy.runtime["reconcile"].policy, "AddJobFlowSteps") && !strcontains(aws_iam_role_policy.runtime["api"].policy, "AddJobFlowSteps")
    error_message = "Only the worker may submit EMR steps."
  }
}
