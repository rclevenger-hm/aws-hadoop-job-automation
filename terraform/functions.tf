resource "aws_cloudwatch_log_group" "runtime" {
  for_each          = toset(["api", "worker", "reconcile"])
  name              = "/aws/lambda/${local.prefix}-${each.key}"
  retention_in_days = 30
}
