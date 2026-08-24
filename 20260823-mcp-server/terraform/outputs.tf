output "artifact_repository" {
  value = google_artifact_registry_repository.mcp.name
}

output "cloud_run_service" {
  value = google_cloud_run_v2_service.mcp.name
}

output "cloud_run_url" {
  value = google_cloud_run_v2_service.mcp.uri
}

output "cloud_run_runtime_service_account" {
  value = google_service_account.cloud_run_runtime.email
}

output "test_invoker_service_account" {
  value = google_service_account.test_invoker.email
}

output "gke_cluster" {
  value = try(google_container_cluster.mcp[0].name, null)
}

output "gke_workload_service_account" {
  value = try(google_service_account.gke_workload[0].email, null)
}

output "agent_runtime" {
  value = google_vertex_ai_reasoning_engine.runtime.id
}

output "agent_runtime_effective_identity" {
  value = google_vertex_ai_reasoning_engine.runtime.spec[0].effective_identity
}

output "agent_gateway" {
  value = local.agent_gateway_id
}

output "agent_runtime_repository" {
  value = google_artifact_registry_repository.agent_runtime.name
}

output "cloud_run_registry_service" {
  value = google_agent_registry_service.cloud_run.id
}

output "cloud_run_registry_endpoint" {
  value = data.google_agent_registry_mcp_server.cloud_run.id
}

output "gke_registry_service" {
  value = try(google_agent_registry_service.gke[0].id, null)
}

output "mcp_caller_service_account" {
  value = try(google_service_account.mcp_caller[0].email, null)
}
