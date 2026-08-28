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

# google-nightly is required here because the stable provider does not yet
# expose the Agent Gateway deployment block. The Runtime remains
# consumer-owned; the Gateway ID is an explicit, validated common handoff.
resource "google_vertex_ai_reasoning_engine" "runtime" {
  provider = google-nightly

  project      = data.google_project.current.number
  region       = var.location
  display_name = var.display_name

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
          agent_gateway = var.agent_gateway_id
        }
      }

      env {
        name  = "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"
        value = "true"
      }
    }
  }

  depends_on = [google_project_service.services["aiplatform.googleapis.com"]]

  # Agent Runtime returns a server-generated contextSpec even when no
  # consumer context configuration is requested. It is not part of this
  # validation contract and must not cause a Runtime update on refresh.
  lifecycle {
    ignore_changes = [context_spec]
  }
}
