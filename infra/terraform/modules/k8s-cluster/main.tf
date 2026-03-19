variable "name" { type = string }
variable "region" { type = string }
variable "private_subnet" { type = list(string) }
variable "tags" { type = map(string) }

locals {
  cluster_name = "${var.name}-${var.region}"
}
