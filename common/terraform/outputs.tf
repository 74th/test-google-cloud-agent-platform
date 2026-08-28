output "agent_gateway_id" {
  description = "Fully qualified shared Agent Gateway resource ID for explicit consumer input."
  value       = google_network_services_agent_gateway.shared.id
}

output "network_id" {
  description = "Fully qualified ID of the dedicated shared VPC."
  value       = google_compute_network.agent_gateway.id
}

output "subnetwork_id" {
  description = "Fully qualified ID of the dedicated PSC interface subnet."
  value       = google_compute_subnetwork.agent_gateway.id
}

output "network_attachment_id" {
  description = "Fully qualified URI of the PSC interface Network Attachment used by Agent Gateway."
  value       = google_compute_network_attachment.agent_gateway.self_link
}

output "agent_gateway_etag" {
  description = "Current Gateway etag for read-back and guarded review; never use as a credential."
  value       = google_network_services_agent_gateway.shared.etag
}

output "agent_gateway_protocols" {
  description = "Configured Gateway protocols for non-secret read-back."
  value       = google_network_services_agent_gateway.shared.protocols
}

output "agent_gateway_registries" {
  description = "Configured Agent Registry resource paths for non-secret read-back."
  value       = google_network_services_agent_gateway.shared.registries
}

output "agent_gateway_governed_access_path" {
  description = "Configured Google-managed Gateway access path."
  value       = google_network_services_agent_gateway.shared.google_managed[0].governed_access_path
}

output "agent_gateway_network_attachment" {
  description = "Configured Gateway egress Network Attachment URI."
  value       = google_network_services_agent_gateway.shared.network_config[0].egress[0].network_attachment
}

output "iap_authz_extension_id" {
  description = "DRY_RUN IAP Authz Extension attached through the common-owned AuthzPolicy."
  value       = google_network_services_authz_extension.iap.id
}

output "iap_authz_policy_id" {
  description = "Common-owned AuthzPolicy targeting the shared Agent Gateway."
  value       = google_network_security_authz_policy.iap.id
}
