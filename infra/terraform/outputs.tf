output "cluster_name" {
  description = "Production Kubernetes cluster name."
  value       = module.k8s_cluster.cluster_name
}

output "vpc_id" {
  description = "Primary VPC identifier."
  value       = module.networking.vpc_id
}

output "vault_kms_key_alias" {
  description = "KMS alias used by Vault auto-unseal."
  value       = module.vault_ha.kms_key_alias
}
