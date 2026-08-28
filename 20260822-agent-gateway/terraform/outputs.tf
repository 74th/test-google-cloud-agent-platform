output "artifact_registry_repository_id" {
  description = "Dedicated Docker repository ID."
  value       = google_artifact_registry_repository.agent_images.repository_id
}

output "artifact_registry_repository" {
  description = "Full Artifact Registry repository name."
  value       = google_artifact_registry_repository.agent_images.name
}

output "agent_gateway_id" {
  description = "Validated common-owned Gateway handoff passed to deployment tooling."
  value       = var.agent_gateway_id
}

output "runtime_effective_identity" {
  description = "Effective identity read from the consumer-owned Runtime."
  value       = google_vertex_ai_reasoning_engine.runtime.spec[0].effective_identity
}

output "runtime_name" {
  description = "Fully qualified consumer-owned Runtime resource name."
  value       = google_vertex_ai_reasoning_engine.runtime.id
}
