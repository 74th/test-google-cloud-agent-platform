locals {
  runtime_class_methods = [
    {
      name       = "query"
      api_mode   = ""
      parameters = { type = "object", properties = { message = { type = "string" } }, required = ["message"] }
    },
    {
      name       = "stream_query"
      api_mode   = "stream"
      parameters = { type = "object", properties = { message = { type = "string" } }, required = ["message"] }
    },
  ]
}

# Test case 1: no Agent Gateway association. run_query_job against this
# Runtime is expected to succeed (baseline).
resource "google_vertex_ai_reasoning_engine" "no_gateway" {
  provider = google-nightly

  project      = data.google_project.current.number
  region       = var.region
  display_name = var.no_gateway_display_name

  spec {
    agent_framework = "custom"
    class_methods   = jsonencode(local.runtime_class_methods)
    identity_type   = "AGENT_IDENTITY"

    container_spec {
      image_uri = var.runtime_image_uri
    }

    deployment_spec {
      env {
        name  = "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"
        value = "true"
      }
    }
  }

  depends_on = [google_project_service.required["aiplatform.googleapis.com"]]

  lifecycle {
    ignore_changes = [context_spec]
  }
}

# Test cases 2 and 3: associated with this repro's own Agent Gateway.
# query/stream_query (case 2) are expected to succeed; run_query_job
# (case 3) is expected to fail with the SSL error this repository documents.
resource "google_vertex_ai_reasoning_engine" "gateway" {
  provider = google-nightly

  project      = data.google_project.current.number
  region       = var.region
  display_name = var.gateway_display_name

  spec {
    agent_framework = "custom"
    class_methods   = jsonencode(local.runtime_class_methods)
    identity_type   = "AGENT_IDENTITY"

    container_spec {
      image_uri = var.runtime_image_uri
    }

    deployment_spec {
      agent_gateway_config {
        agent_to_anywhere_config {
          agent_gateway = google_network_services_agent_gateway.repro.id
        }
      }

      env {
        name  = "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"
        value = "true"
      }
    }
  }

  depends_on = [google_project_service.required["aiplatform.googleapis.com"]]

  lifecycle {
    ignore_changes = [context_spec]
  }
}

# The query-job GCS input/output download is performed by the Runtime's own
# effective identity (not the aiplatform-re service agent alone), so each
# Runtime needs direct object access on the query-job bucket.
resource "google_storage_bucket_iam_member" "query_job_no_gateway_runtime" {
  bucket = google_storage_bucket.query_jobs.name
  role   = "roles/storage.objectAdmin"
  member = "principal://${google_vertex_ai_reasoning_engine.no_gateway.spec[0].effective_identity}"
}

resource "google_storage_bucket_iam_member" "query_job_gateway_runtime" {
  bucket = google_storage_bucket.query_jobs.name
  role   = "roles/storage.objectAdmin"
  member = "principal://${google_vertex_ai_reasoning_engine.gateway.spec[0].effective_identity}"
}

# Authorize only the Gateway-associated Runtime's identity to reach the
# github.com Registry Service. The no-gateway Runtime never goes through
# the Gateway, and tohoho-web.com has no Registry Service at all, so it
# stays default-denied for both.
resource "google_iap_agent_registry_endpoint_iam_member" "github_gateway_runtime" {
  provider = google-nightly

  project     = var.project_id
  location    = var.region
  endpoint_id = data.google_agent_registry_endpoint.github.endpoint_id
  role        = "roles/iap.egressor"
  member      = "principal://${google_vertex_ai_reasoning_engine.gateway.spec[0].effective_identity}"
}
