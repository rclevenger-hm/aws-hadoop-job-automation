# Contributing

Use Python 3.12+ and the hash-locked development requirements. Run Ruff, pytest, contract checks, dependency auditing, artifact build and Terraform format/validate/test. Keep tests, local AWS credentials, state and build outputs out of the deployment artifact.

## Reliability changes

Do not enable automatic retries on `AddJobFlowSteps`, reset uncertain work to queued, bypass ownership, or replace conditional writes with unconditional updates. Preserve cancellation intent across submission/status races. A new workload type must document its execution-role boundary and native API contract. Add failure-path tests when changing these behaviors.

## Deployment changes

Review IAM and Terraform plans before applying. Keep remote state locking and environment-specific OIDC trust. Live EMR tests are explicitly opt-in because they execute code and incur charges. Pull requests should state which automated and live checks actually ran, including any remaining limitations.
