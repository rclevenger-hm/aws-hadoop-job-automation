resource "aws_sns_topic" "operations" { name = "${local.prefix}-operations" }
resource "aws_sns_topic_subscription" "operations" {
  topic_arn = aws_sns_topic.operations.arn
  protocol  = "email"
  endpoint  = var.notification_email
}
