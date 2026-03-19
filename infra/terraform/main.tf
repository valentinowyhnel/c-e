module "networking" {
  source = "./modules/networking"

  name   = var.name
  region = var.region
  tags   = var.tags
}

module "k8s_cluster" {
  source = "./modules/k8s-cluster"

  name           = var.name
  region         = var.region
  private_subnet = module.networking.private_subnet_ids
  tags           = var.tags
}

module "vault_ha" {
  source = "./modules/vault-ha"

  name          = var.name
  region        = var.region
  cluster_name  = module.k8s_cluster.cluster_name
  kms_key_alias = "${var.name}-vault-unseal"
  tags          = var.tags
}

module "postgres_ha" {
  source = "./modules/postgres-ha"

  name         = var.name
  region       = var.region
  cluster_name = module.k8s_cluster.cluster_name
  tags         = var.tags
}

module "valkey" {
  source = "./modules/valkey"

  name      = var.name
  region    = var.region
  subnet_ids = module.networking.private_subnet_ids
  tags      = var.tags
}

module "neo4j" {
  source = "./modules/neo4j"

  name         = var.name
  region       = var.region
  cluster_name = module.k8s_cluster.cluster_name
  tags         = var.tags
}

module "nats" {
  source = "./modules/nats"

  name         = var.name
  region       = var.region
  cluster_name = module.k8s_cluster.cluster_name
  tags         = var.tags
}

module "cloudfront" {
  source = "./modules/cloudfront"

  name             = var.name
  region           = var.region
  console_dns_name = "console.${var.name}.example.com"
  tags             = var.tags
}

module "monitoring" {
  source = "./modules/monitoring"

  name         = var.name
  region       = var.region
  cluster_name = module.k8s_cluster.cluster_name
  tags         = var.tags
}
