variable "project_id" { type = string }
variable "location" { type = string }
variable "query_job_bucket_name" { type = string }

variable "registry_project_id" {
  description = "Project that owns the Registry referenced by the shared common-egress Gateway."
  type        = string
  default     = "nnyn-dev"

  validation {
    condition     = var.registry_project_id == "nnyn-dev"
    error_message = "registry_project_id must remain the reviewed common-egress Registry project."
  }
}

variable "registry_location" {
  description = "Location of the Registry referenced by the shared common-egress Gateway."
  type        = string
  default     = "us-central1"

  validation {
    condition     = var.registry_location == "us-central1"
    error_message = "registry_location must remain the reviewed common-egress Registry location."
  }
}

variable "gcs_registry_service_id" {
  description = "BYOC-owned Registry Service ID for query-job GCS egress."
  type        = string
  default     = "byoc-query-job-storage-20260828"

  validation {
    condition     = can(regex("^byoc-query-job-storage-[0-9]{8}$", var.gcs_registry_service_id))
    error_message = "gcs_registry_service_id must be a dated BYOC query-job service ID."
  }
}

variable "runtime_effective_identity" {
  description = "Effective identity read from the specific common-egress BYOC Runtime GET."
  type        = string

  validation {
    condition = can(regex(
      "^agents\\.global\\.proj-[0-9]+\\.system\\.id\\.goog/resources/aiplatform/projects/[0-9]+/locations/[a-z0-9-]+/reasoningEngines/[0-9]+$",
      var.runtime_effective_identity,
    ))
    error_message = "runtime_effective_identity must be the redacted-safe AGENT_IDENTITY effective identity from Runtime GET."
  }
}
