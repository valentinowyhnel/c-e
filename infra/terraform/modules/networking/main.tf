variable "name" { type = string }
variable "region" { type = string }
variable "tags" { type = map(string) }

locals {
  vpc_id             = "${var.name}-${var.region}-vpc"
  private_subnet_ids = ["${var.name}-${var.region}-private-a", "${var.name}-${var.region}-private-b"]
}
