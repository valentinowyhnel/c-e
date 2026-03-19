variable "name" {
  description = "Deployment name prefix."
  type        = string
  default     = "cortex"
}

variable "cloud" {
  description = "Target cloud provider."
  type        = string
  default     = "aws"

  validation {
    condition     = contains(["aws", "azure"], var.cloud)
    error_message = "cloud must be aws or azure."
  }
}

variable "region" {
  description = "Primary deployment region."
  type        = string
  default     = "eu-west-1"
}

variable "tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
  default = {
    project     = "cortex"
    environment = "production"
    managed_by  = "terraform"
  }
}
