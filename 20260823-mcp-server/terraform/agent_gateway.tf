# The project already has an active AGENT_TO_ANYWHERE gateway. Reuse it via
# var.agent_gateway_id; this experiment must not create a second gateway in
# the same project and direction.
/*
resource "google_network_services_agent_gateway" "egress" {
  provider = google-nightly

  project     = var.project_id
  location    = var.region
  name        = var.agent_gateway_name
  description = "20260823 default-deny Agent Runtime MCP egress gateway"
  labels      = local.common_labels
  protocols   = ["MCP"]
  registries  = [local.registry_path]

  google_managed {
    governed_access_path = "AGENT_TO_ANYWHERE"
  }

  timeouts {
    create = "30m"
    update = "30m"
    delete = "30m"
  }

  depends_on = [
    google_project_service.required,
  ]
}

resource "google_network_services_authz_extension" "iap" {
  provider = google-nightly

  project   = var.project_id
  location  = var.region
  name      = "${var.name_prefix}-iap-authz"
  service   = "iap.googleapis.com"
  fail_open = false
  timeout   = "1s"
  metadata = {
    iamEnforcementMode = "ENFORCE"
    iapPolicyVersion   = "V1"
  }

  depends_on = [google_project_service.required]
}

resource "google_network_security_authz_policy" "iap" {
  provider = google-nightly

  project        = var.project_id
  location       = var.region
  name           = "${var.name_prefix}-iap-policy"
  policy_profile = "REQUEST_AUTHZ"
  action         = "CUSTOM"

  target {
    resources = [google_network_services_agent_gateway.egress.id]
  }

  custom_provider {
    authz_extension {
      resources = [google_network_services_authz_extension.iap.id]
    }
  }

  depends_on = [
    google_network_services_agent_gateway.egress,
    google_network_services_authz_extension.iap,
  ]
}
*/
