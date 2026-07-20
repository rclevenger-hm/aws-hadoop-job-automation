resource "aws_cloudwatch_log_group" "runtime" {
  for_each          = toset(["api", "worker", "reconcile"])
  name              = "/aws/lambda/${local.prefix}-${each.key}"
  retention_in_days = 30
}
resource "aws_lambda_function" "service" {
  for_each                       = toset(["api", "worker", "reconcile"])
  function_name                  = "${local.prefix}-${each.key}"
  role                           = aws_iam_role.runtime[each.key].arn
  runtime                        = "python3.13"
  handler                        = "app.handlers.${each.key}_handler"
  filename                       = "${path.module}/../artifacts/lambda.zip"
  source_code_hash               = fileexists("${path.module}/../artifacts/lambda.zip") ? filebase64sha256("${path.module}/../artifacts/lambda.zip") : null
  architectures                  = ["arm64"]
  memory_size                    = 256
  timeout                        = each.key == "reconcile" ? 120 : 30
  reserved_concurrent_executions = each.key == "api" ? 10 : each.key == "worker" ? 2 : 1
  environment { variables = local.env }
  depends_on = [aws_iam_role_policy.runtime, aws_cloudwatch_log_group.runtime]
  lifecycle {
    precondition {
      condition     = fileexists("${path.module}/../artifacts/lambda.zip")
      error_message = "Run python scripts/build.py before Terraform plan/apply."
    }
  }
}
