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
