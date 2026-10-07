variable "region" {
  type    = string
  default = "us-east-1"
}
variable "name" {
  type    = string
  default = "hadoop"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{3,19}$", var.name))
    error_message = "Use a 4–20 character lowercase service name."
  }
}
variable "environment" {
  type    = string
  default = "dev"
  validation {
    condition     = contains(["dev", "stage", "prod"], var.environment)
    error_message = "Choose dev, stage or prod."
  }
}
variable "cluster_profiles" {
  type = map(object({
    cluster_id         = string
    allowed_principals = list(string)
    jar_prefixes       = list(string)
    input_prefixes     = list(string)
    output_prefixes    = list(string)
    log_uri            = string
  }))
  validation {
    condition     = length(var.cluster_profiles) >= 1 && length(var.cluster_profiles) <= 5 && length(jsonencode(var.cluster_profiles)) <= 2800
    error_message = "Provide 1–5 profiles fitting in 2800 JSON characters (Lambda environment budget)."
  }
  validation {
    condition     = alltrue([for name, p in var.cluster_profiles : can(regex("^[a-z][a-z0-9-]{2,39}$", name)) && can(regex("^j-[A-Z0-9]+$", p.cluster_id)) && length(p.allowed_principals) > 0 && alltrue([for a in p.allowed_principals : can(regex("^arn:aws(-us-gov|-cn)?:iam::[0-9]{12}:(role|user)/[A-Za-z0-9+=,.@_-]+$", a))])])
    error_message = "Use valid cluster IDs and explicit consumer role/user ARNs without IAM paths."
  }
  validation {
    condition     = alltrue([for p in values(var.cluster_profiles) : length(p.jar_prefixes) > 0 && length(p.input_prefixes) > 0 && length(p.output_prefixes) > 0 && alltrue([for uri in concat(p.jar_prefixes, p.input_prefixes, p.output_prefixes, [p.log_uri]) : can(regex("^(s3://[^/]+|hdfs://[^/]*)/[^*?%#\\\\]*/$", uri)) && !strcontains(uri, "/../") && !strcontains(uri, "/./")]) && alltrue([for uri in concat(p.jar_prefixes, [p.log_uri]) : startswith(uri, "s3://")])])
    error_message = "Use canonical directory URIs ending in /; JAR and log prefixes must use S3, without wildcards or traversal."
  }
}
variable "daily_job_limit" {
  type    = number
  default = 100
  validation {
    condition     = var.daily_job_limit >= 1 && var.daily_job_limit <= 10000 && floor(var.daily_job_limit) == var.daily_job_limit
    error_message = "Daily accepted-job limit must be an integer from 1 to 10000."
  }
}
variable "requests_per_minute" {
  type    = number
  default = 60
  validation {
    condition     = var.requests_per_minute >= 1 && var.requests_per_minute <= 10000 && floor(var.requests_per_minute) == var.requests_per_minute
    error_message = "Request limit must be an integer from 1 to 10000."
  }
}
variable "retention_days" {
  type    = number
  default = 30
  validation {
    condition     = var.retention_days >= 1 && var.retention_days <= 365 && floor(var.retention_days) == var.retention_days
    error_message = "Terminal metadata retention must be 1–365 whole days."
  }
}
variable "notification_email" {
  type = string
  validation {
    condition     = can(regex("^[^@ ]+@[^@ ]+\\.[^@ ]+$", var.notification_email))
    error_message = "Provide an operator notification email."
  }
}
variable "monthly_budget" {
  type    = number
  default = 100
  validation {
    condition     = var.monthly_budget > 0
    error_message = "Budget must be positive."
  }
}
variable "log_kms_key_arns" {
  type        = list(string)
  default     = []
  description = "Existing log encryption keys; their key policies must also allow the API role."
}
