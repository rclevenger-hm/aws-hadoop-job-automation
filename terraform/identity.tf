resource "aws_iam_role" "runtime" {
  for_each           = toset(["api", "worker", "reconcile"])
  name               = "${local.prefix}-${each.key}"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
locals {
  runtime_statements = { for kind in ["api", "worker", "reconcile"] : kind => concat([
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.runtime[kind].arn}:*" },
    { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"], Resource = [aws_dynamodb_table.jobs.arn, "${aws_dynamodb_table.jobs.arn}/index/*"] }
    ], contains(["api", "reconcile"], kind) ? [
    { Effect = "Allow", Action = ["sqs:SendMessage"], Resource = aws_sqs_queue.jobs.arn }
    ] : [], kind == "worker" ? [
    { Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = aws_sqs_queue.jobs.arn }
    ] : [], [for p in values(var.cluster_profiles) : {
      Effect    = "Allow", Action = ["elasticmapreduce:AddJobFlowSteps"],
      Resource  = "arn:${data.aws_partition.current.partition}:elasticmapreduce:${var.region}:${data.aws_caller_identity.current.account_id}:cluster/${p.cluster_id}",
      Condition = { Null = { "elasticmapreduce:ExecutionRoleArn" = "true" } }
    } if kind == "worker"], kind == "reconcile" ? [
    { Effect = "Allow", Action = ["elasticmapreduce:ListSteps", "elasticmapreduce:DescribeStep", "elasticmapreduce:CancelSteps"], Resource = local.cluster_arns }
    ] : [], kind == "api" ? [
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = local.log_arns }
    ] : [], kind == "api" && length(var.log_kms_key_arns) > 0 ? [
    { Effect = "Allow", Action = ["kms:Decrypt"], Resource = var.log_kms_key_arns, Condition = { StringEquals = { "kms:ViaService" = "s3.${var.region}.amazonaws.com" } } }
    ] : [])
  }
}
resource "aws_iam_role_policy" "runtime" {
  for_each = aws_iam_role.runtime
  role     = each.value.id
  policy   = jsonencode({ Version = "2012-10-17", Statement = local.runtime_statements[each.key] })
}
