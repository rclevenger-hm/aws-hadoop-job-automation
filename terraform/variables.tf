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
