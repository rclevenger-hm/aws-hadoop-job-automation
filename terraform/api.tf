resource "aws_api_gateway_rest_api" "service" {
  name = local.prefix
  endpoint_configuration { types = ["REGIONAL"] }
}
resource "aws_api_gateway_rest_api_policy" "service" {
  rest_api_id = aws_api_gateway_rest_api.service.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Principal = { AWS = local.consumers }, Action = "execute-api:Invoke", Resource = "${aws_api_gateway_rest_api.service.execution_arn}/*" },
    { Effect = "Deny", Principal = "*", Action = "execute-api:Invoke", Resource = "${aws_api_gateway_rest_api.service.execution_arn}/*", Condition = { ArnNotEquals = { "aws:PrincipalArn" = local.consumers } } }
  ] })
}
resource "aws_api_gateway_resource" "jobs" {
  rest_api_id = aws_api_gateway_rest_api.service.id
  parent_id   = aws_api_gateway_rest_api.service.root_resource_id
  path_part   = "jobs"
}
resource "aws_api_gateway_resource" "job" {
  rest_api_id = aws_api_gateway_rest_api.service.id
  parent_id   = aws_api_gateway_resource.jobs.id
  path_part   = "{job_id}"
}
resource "aws_api_gateway_resource" "cancel" {
  rest_api_id = aws_api_gateway_rest_api.service.id
  parent_id   = aws_api_gateway_resource.job.id
  path_part   = "cancel"
}
resource "aws_api_gateway_resource" "logs" {
  rest_api_id = aws_api_gateway_rest_api.service.id
  parent_id   = aws_api_gateway_resource.job.id
  path_part   = "logs"
}
resource "aws_api_gateway_resource" "usage" {
  rest_api_id = aws_api_gateway_rest_api.service.id
  parent_id   = aws_api_gateway_rest_api.service.root_resource_id
  path_part   = "usage"
}
locals {
  routes = {
    submit = { id = aws_api_gateway_resource.jobs.id, method = "POST" }
    list   = { id = aws_api_gateway_resource.jobs.id, method = "GET" }
    status = { id = aws_api_gateway_resource.job.id, method = "GET" }
    cancel = { id = aws_api_gateway_resource.cancel.id, method = "POST" }
    logs   = { id = aws_api_gateway_resource.logs.id, method = "GET" }
    usage  = { id = aws_api_gateway_resource.usage.id, method = "GET" }
  }
}
resource "aws_api_gateway_method" "route" {
  for_each      = local.routes
  rest_api_id   = aws_api_gateway_rest_api.service.id
  resource_id   = each.value.id
  http_method   = each.value.method
  authorization = "AWS_IAM"
}
resource "aws_api_gateway_integration" "route" {
  for_each                = local.routes
  rest_api_id             = aws_api_gateway_rest_api.service.id
  resource_id             = each.value.id
  http_method             = aws_api_gateway_method.route[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.service["api"].invoke_arn
  timeout_milliseconds    = 29000
}
