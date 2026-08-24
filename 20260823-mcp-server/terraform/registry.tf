resource "google_agent_registry_service" "cloud_run" {
  provider = google-nightly

  project      = var.project_id
  location     = var.region
  service_id   = var.cloud_run_registry_service_id
  display_name = "20260823 Cloud Run MCP validation"

  interfaces {
    url              = "${google_cloud_run_v2_service.mcp.uri}/mcp"
    protocol_binding = "JSONRPC"
  }

  mcp_server_spec {
    type    = "TOOL_SPEC"
    content = local.tool_spec_content
  }

  depends_on = [google_cloud_run_v2_service_iam_member.mcp_caller]
}

resource "google_agent_registry_service" "gke" {
  count    = var.enable_gke ? 1 : 0
  provider = google-nightly

  project      = var.project_id
  location     = var.region
  service_id   = var.gke_registry_service_id
  display_name = "20260823 GKE MCP validation"

  interfaces {
    url              = "https://${var.gke_mcp_hostname}/mcp"
    protocol_binding = "JSONRPC"
  }

  mcp_server_spec {
    type    = "TOOL_SPEC"
    content = local.tool_spec_content
  }

  lifecycle {
    precondition {
      condition     = var.gke_mcp_hostname != "" && var.gke_auth_audience != ""
      error_message = "GKE Registry registration requires an operator-authorized hostname and exact authentication audience."
    }
  }
}

data "google_agent_registry_mcp_server" "cloud_run" {
  provider = google-nightly

  project  = var.project_id
  location = var.region
  filter   = "displayName=\"20260823 Cloud Run MCP validation\""

  depends_on = [google_agent_registry_service.cloud_run]
}

data "google_agent_registry_mcp_server" "gke" {
  count    = var.enable_gke ? 1 : 0
  provider = google-nightly

  project  = var.project_id
  location = var.region
  filter   = "displayName=\"20260823 GKE MCP validation\""

  depends_on = [google_agent_registry_service.gke]
}

# The existing Agent Gateway also governs the Google control-plane call that
# resolves Registry Services. Reuse the endpoint created by the prior Gateway
# experiment and grant only this Runtime principal endpoint-scoped egress.
data "google_agent_registry_endpoint" "agentregistry_control_plane" {
  provider = google-nightly

  project  = var.project_id
  location = var.region
  filter   = "displayName=\"20260822 managed agw-20260822-agentregistry\""
}

resource "google_iap_agent_registry_endpoint_iam_member" "agentregistry_control_plane" {
  provider = google-nightly

  project     = var.project_id
  location    = var.region
  endpoint_id = data.google_agent_registry_endpoint.agentregistry_control_plane.endpoint_id
  role        = "roles/iap.egressor"
  member      = "principal://${google_vertex_ai_reasoning_engine.runtime.spec[0].effective_identity}"
}

data "google_agent_registry_endpoint" "aiplatform_regional_control_plane" {
  provider = google-nightly

  project  = var.project_id
  location = var.region
  filter   = "displayName=\"20260822 managed agw-20260822-aiplatform\""
}

data "google_agent_registry_endpoint" "aiplatform_global_control_plane" {
  provider = google-nightly

  project  = var.project_id
  location = var.region
  filter   = "displayName=\"20260822 managed agw-20260822-aiplatform-global\""
}

resource "google_agent_registry_service" "iamcredentials_control_plane" {
  provider = google-nightly

  project      = var.project_id
  location     = var.region
  service_id   = "${var.name_prefix}-iamcredentials"
  display_name = "20260823 IAM Credentials control-plane endpoint"

  endpoint_spec {
    type = "NO_SPEC"
  }

  interfaces {
    url              = "https://iamcredentials.googleapis.com"
    protocol_binding = "HTTP_JSON"
  }
}

data "google_agent_registry_endpoint" "iamcredentials_control_plane" {
  provider = google-nightly

  project  = var.project_id
  location = var.region
  filter   = "displayName=\"20260823 IAM Credentials control-plane endpoint\""

  depends_on = [google_agent_registry_service.iamcredentials_control_plane]
}

resource "google_iap_agent_registry_endpoint_iam_member" "aiplatform_regional_control_plane" {
  provider = google-nightly

  project     = var.project_id
  location    = var.region
  endpoint_id = data.google_agent_registry_endpoint.aiplatform_regional_control_plane.endpoint_id
  role        = "roles/iap.egressor"
  member      = "principal://${google_vertex_ai_reasoning_engine.runtime.spec[0].effective_identity}"
}

resource "google_iap_agent_registry_endpoint_iam_member" "aiplatform_global_control_plane" {
  provider = google-nightly

  project     = var.project_id
  location    = var.region
  endpoint_id = data.google_agent_registry_endpoint.aiplatform_global_control_plane.endpoint_id
  role        = "roles/iap.egressor"
  member      = "principal://${google_vertex_ai_reasoning_engine.runtime.spec[0].effective_identity}"
}

resource "google_iap_agent_registry_endpoint_iam_member" "iamcredentials_control_plane" {
  provider = google-nightly

  project     = var.project_id
  location    = var.region
  endpoint_id = data.google_agent_registry_endpoint.iamcredentials_control_plane.endpoint_id
  role        = "roles/iap.egressor"
  member      = "principal://${google_vertex_ai_reasoning_engine.runtime.spec[0].effective_identity}"
}

resource "google_iap_agent_registry_mcp_server_iam_member" "cloud_run" {
  provider = google-nightly

  project       = var.project_id
  location      = var.region
  mcp_server_id = data.google_agent_registry_mcp_server.cloud_run.mcp_server_id
  role          = "roles/iap.egressor"
  member        = "principal://${google_vertex_ai_reasoning_engine.runtime.spec[0].effective_identity}"
}

resource "google_iap_agent_registry_mcp_server_iam_member" "gke" {
  count    = var.enable_gke ? 1 : 0
  provider = google-nightly

  project       = var.project_id
  location      = var.region
  mcp_server_id = data.google_agent_registry_mcp_server.gke[0].id
  role          = "roles/iap.egressor"
  member        = "principal://${google_vertex_ai_reasoning_engine.runtime.spec[0].effective_identity}"
}
