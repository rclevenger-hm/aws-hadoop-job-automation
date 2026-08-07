output "endpoint" { value = aws_api_gateway_stage.service.invoke_url }
output "invoke_resource" { value = "${aws_api_gateway_rest_api.service.execution_arn}/${aws_api_gateway_stage.service.stage_name}/*/*" }
output "jobs_table" { value = aws_dynamodb_table.jobs.name }
