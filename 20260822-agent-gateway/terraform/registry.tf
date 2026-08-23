locals {
  registry_services = {
    agentregistry = {
      service_id       = "agw-20260822-agentregistry"
      display_name     = "20260822 managed agw-20260822-agentregistry"
      url              = "https://agentregistry.googleapis.com"
      protocol_binding = "HTTP_JSON"
    }
    logging = {
      service_id       = "agw-20260822-logging"
      display_name     = "20260822 managed agw-20260822-logging"
      url              = "https://logging.googleapis.com"
      protocol_binding = "HTTP_JSON"
    }
    aiplatform = {
      service_id       = "agw-20260822-aiplatform"
      display_name     = "20260822 managed agw-20260822-aiplatform"
      url              = "https://us-central1-aiplatform.googleapis.com"
      protocol_binding = "HTTP_JSON"
    }
    aiplatform_global = {
      service_id       = "agw-20260822-aiplatform-global"
      display_name     = "20260822 managed agw-20260822-aiplatform-global"
      url              = "https://aiplatform.googleapis.com"
      protocol_binding = "HTTP_JSON"
    }
    runtime = {
      service_id       = "agw-20260822-runtime"
      display_name     = "20260822 Agent Gateway runtime endpoint"
      url              = "https://${var.location}-aiplatform.mtls.googleapis.com/v1/${google_vertex_ai_reasoning_engine.runtime.id}"
      protocol_binding = "JSONRPC"
    }
    github = {
      service_id       = "agw-20260822-github"
      display_name     = "20260822 GitHub egress endpoint"
      url              = "https://github.com"
      protocol_binding = "HTTP_JSON"
    }
  }
}

resource "google_agent_registry_service" "services" {
  provider = google-nightly
  for_each = local.registry_services

  project      = var.project_id
  location     = var.location
  service_id   = each.value.service_id
  display_name = each.value.display_name

  endpoint_spec {
    type = "NO_SPEC"
  }

  interfaces {
    url              = each.value.url
    protocol_binding = each.value.protocol_binding
  }
}
