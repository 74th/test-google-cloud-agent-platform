# Shared Registry Services. These resources are common-owned so every
# consumer resolves the same endpoint for a given external domain.
resource "google_agent_registry_service" "github" {
  provider = google-nightly

  project      = var.project_id
  location     = var.region
  service_id   = "agent-gateway-20260828-github"
  display_name = "20260828 shared Gateway GitHub allow endpoint"

  endpoint_spec {
    type = "NO_SPEC"
  }

  interfaces {
    url              = "https://github.com"
    protocol_binding = "HTTP_JSON"
  }
}

resource "google_agent_registry_service" "agentregistry" {
  provider = google-nightly

  project      = var.project_id
  location     = var.region
  service_id   = "mcp-20260823-mcp-server-agentregistry"
  display_name = "mcp-20260823-mcp-server Agent Registry control plane"

  endpoint_spec {
    type = "NO_SPEC"
  }

  interfaces {
    url              = "https://agentregistry.googleapis.com"
    protocol_binding = "HTTP_JSON"
  }
}

resource "google_agent_registry_service" "aiplatform_global" {
  provider = google-nightly

  project      = var.project_id
  location     = var.region
  service_id   = "mcp-20260823-mcp-server-aiplatform-global"
  display_name = "mcp-20260823-mcp-server Vertex AI global control plane"

  endpoint_spec {
    type = "NO_SPEC"
  }

  interfaces {
    url              = "https://aiplatform.googleapis.com"
    protocol_binding = "HTTP_JSON"
  }
}

resource "google_agent_registry_service" "aiplatform_regional" {
  provider = google-nightly

  project      = var.project_id
  location     = var.region
  service_id   = "mcp-20260823-mcp-server-aiplatform"
  display_name = "mcp-20260823-mcp-server Vertex AI regional control plane"

  endpoint_spec {
    type = "NO_SPEC"
  }

  interfaces {
    url              = "https://us-central1-aiplatform.googleapis.com"
    protocol_binding = "HTTP_JSON"
  }
}

resource "google_agent_registry_service" "iamcredentials" {
  provider = google-nightly

  project      = var.project_id
  location     = var.region
  service_id   = "mcp-20260823-mcp-server-iamcredentials"
  display_name = "mcp-20260823-mcp-server IAM Credentials control plane"

  endpoint_spec {
    type = "NO_SPEC"
  }

  interfaces {
    url              = "https://iamcredentials.googleapis.com"
    protocol_binding = "HTTP_JSON"
  }
}

data "google_agent_registry_endpoint" "github" {
  provider = google-nightly

  project  = var.project_id
  location = var.region
  filter   = "displayName=\"20260828 shared Gateway GitHub allow endpoint\""

  depends_on = [google_agent_registry_service.github]
}

data "google_agent_registry_endpoint" "aiplatform_global" {
  provider = google-nightly

  project  = var.project_id
  location = var.region
  filter   = "displayName=\"mcp-20260823-mcp-server Vertex AI global control plane\""

  depends_on = [google_agent_registry_service.aiplatform_global]
}
