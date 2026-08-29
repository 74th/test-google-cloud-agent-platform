# Common-owned Registry endpoints are read-only dependencies of this consumer.
# The consumer must not create, import, or mutate these services or endpoints.
locals {
  common_endpoint_display_names = {
    github              = "20260828 shared Gateway GitHub allow endpoint"
    agentregistry       = "mcp-20260823-mcp-server Agent Registry control plane"
    aiplatform_global   = "mcp-20260823-mcp-server Vertex AI global control plane"
    aiplatform_regional = "mcp-20260823-mcp-server Vertex AI regional control plane"
    iamcredentials      = "mcp-20260823-mcp-server IAM Credentials control plane"
  }
}

data "google_agent_registry_endpoint" "common" {
  for_each = local.common_endpoint_display_names
  provider = google

  project  = var.project_id
  location = var.region
  filter   = "displayName=\"${each.value}\""
}
