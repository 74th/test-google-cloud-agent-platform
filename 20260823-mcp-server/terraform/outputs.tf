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

output "gke_internal_https_ip" {
  value = try(google_compute_address.gke_internal_https[0].address, null)
}

output "gke_private_dns_zone" {
  value = try(google_dns_managed_zone.gke_private[0].name, null)
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

output "agent_gateway_preflight_id" {
  description = "Exact shared Gateway ID that must pass scripts/gateway_preflight.py before deployment."
  value       = "projects/nnyn-dev/locations/us-central1/agentGateways/common-egress"
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

output "agentregistry_control_plane_service" {
  value = google_agent_registry_service.agentregistry_control_plane.id
}

output "aiplatform_regional_control_plane_service" {
  value = google_agent_registry_service.aiplatform_regional_control_plane.id
}

output "aiplatform_global_control_plane_service" {
  value = google_agent_registry_service.aiplatform_global_control_plane.id
}

output "iamcredentials_control_plane_service" {
  value = google_agent_registry_service.iamcredentials_control_plane.id
}

output "gke_registry_service" {
  value = try(google_agent_registry_service.gke[0].id, null)
}

output "mcp_caller_service_account" {
  value = try(google_service_account.mcp_caller[0].email, null)
}
