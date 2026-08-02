output "repository" { value = google_artifact_registry_repository.verification.name }
output "runtime_service_account" { value = google_service_account.runtime.email }
output "query_job_bucket" { value = google_storage_bucket.query_jobs.url }
