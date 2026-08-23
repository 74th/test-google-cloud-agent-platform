output "artifact_registry_repository_id" {
  description = "Dedicated Docker repository ID."
  value       = google_artifact_registry_repository.agent_images.repository_id
}

output "artifact_registry_repository" {
  description = "Full Artifact Registry repository name."
  value       = google_artifact_registry_repository.agent_images.name
}

output "agent_gateway_id" {
  description = "Full Agent Gateway resource name."
  value       = google_network_services_agent_gateway.egress.id
}

output "agent_gateway_root_certificates" {
  description = "Root CA certificates needed by a BYOC image after gateway creation."
  value       = one(google_network_services_agent_gateway.egress.agent_gateway_card[*].root_certificates)
  sensitive   = true
}

output "agent_registry_path" {
  description = "Regional registry consumed by Agent Gateway."
  value       = local.registry_path
}

output "runtime_name" {
  description = "Full Agent Runtime resource name."
  value       = google_vertex_ai_reasoning_engine.runtime.id
}

output "runtime_effective_identity" {
  description = "Agent Identity effective principal for the Runtime."
  value       = google_vertex_ai_reasoning_engine.runtime.spec[0].effective_identity
}
