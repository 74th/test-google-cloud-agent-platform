data "google_project" "current" {
  project_id = var.project_id
}

locals {
  runtime_class_methods = jsonencode([
    {
      name     = "query"
      api_mode = ""
      parameters = {
        type       = "object"
        properties = { target = { type = "string" }, message = { type = "string" } }
        required   = ["target", "message"]
      }
    },
    {
      name     = "stream_query"
      api_mode = "stream"
      parameters = {
        type       = "object"
        properties = { target = { type = "string" }, message = { type = "string" } }
        required   = ["target", "message"]
      }
    },
  ])
}

resource "google_vertex_ai_reasoning_engine" "runtime" {
  provider = google-nightly

  project      = data.google_project.current.number
  region       = var.region
  display_name = var.agent_runtime_name
  labels       = local.common_labels

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
      image_uri = local.agent_runtime_image
    }

    deployment_spec {
      agent_gateway_config {
        agent_to_anywhere_config {
          agent_gateway = local.agent_gateway_id
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
      env {
        name  = "REGISTRY_PROJECT"
        value = var.project_id
      }
      env {
        name  = "REGISTRY_LOCATION"
        value = var.region
      }
      env {
        name  = "CLOUD_RUN_ALLOWED_HOSTS"
        value = regex("^https://([^/]+)", google_cloud_run_v2_service.mcp.uri)[0]
      }
      env {
        name  = "CLOUD_RUN_REGISTRY_SERVICE_ID"
        value = var.cloud_run_registry_service_id
      }
      env {
        name  = "GKE_REGISTRY_SERVICE_ID"
        value = var.gke_registry_service_id
      }
      env {
        name  = "CLOUD_RUN_AUTH_AUDIENCE"
        value = var.cloud_run_auth_audience != "" ? var.cloud_run_auth_audience : google_cloud_run_v2_service.mcp.uri
      }
      dynamic "env" {
        for_each = var.enable_gke ? [1] : []
        content {
          name  = "GKE_AUTH_AUDIENCE"
          value = var.gke_auth_audience
        }
      }
      dynamic "env" {
        for_each = var.enable_gke ? [1] : []
        content {
          name  = "GKE_ALLOWED_HOSTS"
          value = var.gke_mcp_hostname
        }
      }
      env {
        name  = "MCP_CALLER_SERVICE_ACCOUNT"
        value = var.use_mcp_caller_service_account ? google_service_account.mcp_caller[0].email : ""
      }
    }
  }

  lifecycle {
    precondition {
      condition     = can(regex("@sha256:[0-9a-f]{64}$", local.agent_runtime_image))
      error_message = "Agent Runtime must use an immutable image digest."
    }
  }

  depends_on = [
    google_project_service.required,
    google_artifact_registry_repository.agent_runtime,
    google_artifact_registry_repository_iam_member.agent_runtime_reader,
  ]
}
