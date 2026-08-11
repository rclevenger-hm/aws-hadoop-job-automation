output "endpoint" { value = aws_api_gateway_stage.service.invoke_url }
output "invoke_resource" { value = "${aws_api_gateway_rest_api.service.execution_arn}/${aws_api_gateway_stage.service.stage_name}/*/*" }
output "jobs_table" { value = aws_dynamodb_table.jobs.name }
output "dead_letter_queue_url" { value = aws_sqs_queue.dead_letter.url }
output "api_role_arn" { value = aws_iam_role.runtime["api"].arn }
