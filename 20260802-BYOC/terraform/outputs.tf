output "repository" { value = google_artifact_registry_repository.verification.name }
output "runtime_service_account" { value = google_service_account.runtime.email }
output "query_job_bucket" { value = google_storage_bucket.query_jobs.url }
output "query_job_gcs_registry_service" { value = google_agent_registry_service.query_job_gcs.id }
output "query_job_gcs_registry_endpoint" { value = data.google_agent_registry_endpoint.query_job_gcs.endpoint_id }
output "query_job_gcs_endpoint_iam_member" { value = google_iap_agent_registry_endpoint_iam_member.query_job_gcs.member }
