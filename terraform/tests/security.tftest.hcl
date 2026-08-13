mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }
}
variables {
  notification_email = "operator@example.com"
  cluster_profiles = {
    analytics = {
      cluster_id         = "j-EXAMPLE123"
      allowed_principals = ["arn:aws:iam::123456789012:role/Consumer"]
      jar_prefixes       = ["s3://assets/approved/"]
      input_prefixes     = ["s3://data/input/"]
      output_prefixes    = ["s3://data/output/"]
      log_uri            = "s3://logs/clusters/"
    }
  }
}
