locals {
  runtime_class_methods = jsonencode([
    {
      name     = "query"
      api_mode = ""
      parameters = {
        type       = "object"
        properties = { message = { type = "string" } }
        required   = ["message"]
      }
    },
    {
      name     = "stream_query"
      api_mode = "stream"
      parameters = {
        type       = "object"
        properties = { message = { type = "string" } }
        required   = ["message"]
      }
    }
  ])
}

resource "google_vertex_ai_reasoning_engine" "runtime" {
  provider = google-nightly

  project      = data.google_project.current.number
  region       = var.location
  display_name = "20260822-agent-gateway-claude-local-webfetch-r5"

  context_spec {
    memory_bank_config {
      disable_memory_revisions = false
    }
  }

  spec {
    agent_framework = "custom"
    class_methods   = local.runtime_class_methods
    identity_type   = "AGENT_IDENTITY"

    container_spec {
      image_uri = var.runtime_image_uri
    }

    deployment_spec {
      agent_gateway_config {
        agent_to_anywhere_config {
          agent_gateway = google_network_services_agent_gateway.egress.id
        }
      }

      env {
        name  = "CLAUDE_CODE_USE_VERTEX"
        value = "1"
      }
      env {
        name  = "ANTHROPIC_VERTEX_PROJECT_ID"
        value = var.vertex_project_id
      }
      env {
        name  = "CLOUD_ML_REGION"
        value = var.vertex_region
      }
      env {
        name  = "ANTHROPIC_MODEL"
        value = "claude-haiku-4-5@20251001"
      }
      env {
        name  = "ANTHROPIC_DEFAULT_HAIKU_MODEL"
        value = "claude-haiku-4-5@20251001"
      }
      env {
        name  = "VERTEX_REGION_CLAUDE_HAIKU_4_5"
        value = "global"
      }
      env {
        name  = "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"
        value = "true"
      }
    }
  }
}
