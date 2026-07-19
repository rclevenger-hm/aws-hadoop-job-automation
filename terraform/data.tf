resource "aws_dynamodb_table" "jobs" {
  name                        = "${local.prefix}-jobs"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "pk"
  range_key                   = "sk"
  deletion_protection_enabled = true
  point_in_time_recovery { enabled = true }
  server_side_encryption { enabled = true }
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
  dynamic "attribute" {
    for_each = toset(["pk", "sk", "history_pk", "history_sk", "active_pk", "active_sk"])
    content {
      name = attribute.value
      type = "S"
    }
  }
  dynamic "global_secondary_index" {
    for_each = toset(["history", "active"])
    content {
      name            = global_secondary_index.value
      hash_key        = "${global_secondary_index.value}_pk"
      range_key       = "${global_secondary_index.value}_sk"
      projection_type = "ALL"
    }
  }
}
resource "aws_sqs_queue" "dead_letter" {
  name                      = "${local.prefix}-dead-letter"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}
resource "aws_sqs_queue" "jobs" {
  name                       = "${local.prefix}-jobs"
  visibility_timeout_seconds = 180
  message_retention_seconds  = 345600
  sqs_managed_sse_enabled    = true
  redrive_policy             = jsonencode({ deadLetterTargetArn = aws_sqs_queue.dead_letter.arn, maxReceiveCount = 5 })
}
