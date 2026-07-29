resource "aws_sns_topic" "operations" { name = "${local.prefix}-operations" }
