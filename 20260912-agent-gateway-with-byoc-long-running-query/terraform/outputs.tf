output "agent_gateway_id" {
  description = "Fully qualified 20260912 repro Agent Gateway resource ID."
  value       = google_network_services_agent_gateway.repro.id
}

output "artifact_registry_repository" {
  value = google_artifact_registry_repository.agent_images.name
}

output "query_job_bucket" {
  value = google_storage_bucket.query_jobs.name
}

output "no_gateway_runtime_name" {
  description = "Test case 1 Runtime (no Agent Gateway)."
  value       = google_vertex_ai_reasoning_engine.no_gateway.id
}

output "gateway_runtime_name" {
  description = "Test cases 2 and 3 Runtime (associated with the repro Agent Gateway)."
  value       = google_vertex_ai_reasoning_engine.gateway.id
}

output "gateway_runtime_effective_identity" {
  value = google_vertex_ai_reasoning_engine.gateway.spec[0].effective_identity
}

output "github_registry_endpoint_id" {
  value = data.google_agent_registry_endpoint.github.endpoint_id
}
