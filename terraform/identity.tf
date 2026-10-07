resource "aws_iam_role" "runtime" {
  for_each           = toset(["api", "worker", "reconcile"])
  name               = "${local.prefix}-${each.key}"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy" "runtime" {
  for_each = aws_iam_role.runtime
  role     = each.value.id
  policy = jsonencode({ Version = "2012-10-17", Statement = concat([
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.runtime[each.key].arn}:*" },
    { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"], Resource = [aws_dynamodb_table.jobs.arn, "${aws_dynamodb_table.jobs.arn}/index/*"] },
    ], contains(["api", "reconcile"], each.key) ? [
    { Effect = "Allow", Action = ["sqs:SendMessage"], Resource = aws_sqs_queue.jobs.arn }
    ] : [], each.key == "worker" ? concat([
      { Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = aws_sqs_queue.jobs.arn }
      ], [for p in values(var.cluster_profiles) : {
        Effect    = "Allow", Action = ["elasticmapreduce:AddJobFlowSteps"],
        Resource  = "arn:${data.aws_partition.current.partition}:elasticmapreduce:${var.region}:${data.aws_caller_identity.current.account_id}:cluster/${p.cluster_id}",
        Condition = { Null = { "elasticmapreduce:ExecutionRoleArn" = "true" } }
    }]) : [], each.key == "reconcile" ? [
    { Effect = "Allow", Action = ["elasticmapreduce:ListSteps", "elasticmapreduce:DescribeStep", "elasticmapreduce:CancelSteps"], Resource = local.cluster_arns }
    ] : [], each.key == "api" ? [
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = local.log_arns }
    ] : [], each.key == "api" && length(var.log_kms_key_arns) > 0 ? [
    { Effect = "Allow", Action = ["kms:Decrypt"], Resource = var.log_kms_key_arns, Condition = { StringEquals = { "kms:ViaService" = "s3.${var.region}.amazonaws.com" } } }
  ] : []) })
}
