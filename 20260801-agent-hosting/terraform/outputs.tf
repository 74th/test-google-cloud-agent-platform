output "runtime_service_account_email" {
  description = "2026-08-01 20260801-agent-hosting test runtime service account email for scripts/deploy.sh."
  value       = google_service_account.runtime.email
}

output "artifact_registry_repository_id" {
  description = "2026-08-01 20260801-agent-hosting test Docker Artifact Registry repository ID for scripts/deploy.sh."
  value       = google_artifact_registry_repository.agent_images.repository_id
}
