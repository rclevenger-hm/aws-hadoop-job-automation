# Architecture and state transitions

API Gateway requires AWS_IAM on every route and a resource-policy allowlist. The API Lambda derives the tenant from the verified IAM identity, validates the caller's cluster profile and request, then atomically creates a DynamoDB job and reserves one daily admission. It sends only tenant/job hashes to SQS. A failed queue publish leaves recoverable metadata rather than losing the request.

