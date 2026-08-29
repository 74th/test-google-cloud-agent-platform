locals {
  gcs_registry_service_display_name = "20260828 BYOC query-job GCS"
}

resource "google_agent_registry_service" "query_job_gcs" {
  provider = google-nightly

  project      = var.registry_project_id
  location     = var.registry_location
  service_id   = var.gcs_registry_service_id
  display_name = local.gcs_registry_service_display_name

  endpoint_spec {
    type = "NO_SPEC"
  }

  interfaces {
    url              = "https://storage.googleapis.com"
    protocol_binding = "HTTP_JSON"
  }

  interfaces {
    url              = "https://storage.mtls.googleapis.com"
    protocol_binding = "HTTP_JSON"
  }

  lifecycle {
    precondition {
      condition     = var.registry_project_id == "nnyn-dev" && var.registry_location == "us-central1"
      error_message = "BYOC GCS Registry Service must remain in the Registry used by common-egress."
    }
    precondition {
      condition     = can(regex("^byoc-query-job-storage-", var.gcs_registry_service_id))
      error_message = "BYOC GCS Registry Service must remain consumer-owned and collision-resistant."
    }
  }
}

data "google_agent_registry_endpoint" "query_job_gcs" {
  provider = google-nightly

  project  = var.registry_project_id
  location = var.registry_location
  filter   = "displayName=\"${local.gcs_registry_service_display_name}\""

  depends_on = [google_agent_registry_service.query_job_gcs]
}

resource "google_iap_agent_registry_endpoint_iam_member" "query_job_gcs" {
  provider = google-nightly

  project     = var.registry_project_id
  location    = var.registry_location
  endpoint_id = data.google_agent_registry_endpoint.query_job_gcs.endpoint_id
  role        = "roles/iap.egressor"
  member      = "principal://${var.runtime_effective_identity}"

  lifecycle {
    precondition {
      condition     = can(regex("^agents\\.global\\.proj-[0-9]+\\.system\\.id\\.goog/resources/aiplatform/projects/[0-9]+/locations/[a-z0-9-]+/reasoningEngines/[0-9]+$", var.runtime_effective_identity))
      error_message = "Endpoint egress IAM must target only the reviewed Runtime effective identity."
    }
  }
}
