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

  lifecycle {
    precondition {
      condition     = can(regex("^mcp-20260823-", var.cloud_run_registry_service_id))
      error_message = "Cloud Run Registry Service must remain consumer-owned and collision-resistant."
    }
  }
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
    precondition {
      condition     = can(regex("^mcp-20260823-", var.gke_registry_service_id))
      error_message = "GKE Registry Service must remain consumer-owned and collision-resistant."
    }
  }
}

data "google_agent_registry_mcp_server" "cloud_run" {
  provider = google

  project  = var.project_id
  location = var.region
  filter   = "displayName=\"20260823 Cloud Run MCP validation\""

  depends_on = [google_agent_registry_service.cloud_run]
}

data "google_agent_registry_mcp_server" "gke" {
  count    = var.enable_gke ? 1 : 0
  provider = google

  project  = var.project_id
  location = var.region
  filter   = "displayName=\"20260823 GKE MCP validation\""

  depends_on = [google_agent_registry_service.gke]
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
  mcp_server_id = data.google_agent_registry_mcp_server.gke[0].mcp_server_id
  role          = "roles/iap.egressor"
  member        = "principal://${google_vertex_ai_reasoning_engine.runtime.spec[0].effective_identity}"
}
