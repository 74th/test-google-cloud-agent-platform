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
