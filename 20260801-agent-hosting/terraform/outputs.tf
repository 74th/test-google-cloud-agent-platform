output "runtime_service_account_email" {
  description = "2026-08-01 20260801-agent-hosting test runtime service account email for scripts/deploy.sh."
  value       = google_service_account.runtime.email
}
