terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}

locals {
  common_labels = merge(var.labels, {
    project = "agent-gateway-egress"
  })
  registry_path = "//agentregistry.googleapis.com/projects/${var.project_id}/locations/${var.location}"
}

resource "google_project_service" "services" {
  for_each = toset([
    "agentregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "networkservices.googleapis.com",
    "networksecurity.googleapis.com",
    "serviceusage.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_artifact_registry_repository" "agent_images" {
  project       = var.project_id
  location      = var.location
  repository_id = "agent-gateway-20260822"
  description   = "20260822 Agent Gateway egress validation container images."
  format        = "DOCKER"
  labels        = local.common_labels

  depends_on = [google_project_service.services["artifactregistry.googleapis.com"]]
}

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "agent-gateway-20260822-runtime"
  display_name = "20260822 Agent Gateway validation runtime"
  description  = "Dedicated runtime identity for the 20260822 Agent Gateway validation."
}

resource "google_project_iam_member" "runtime_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_artifact_registry_repository_iam_member" "agent_runtime_reader" {
  project    = var.project_id
  location   = google_artifact_registry_repository.agent_images.location
  repository = google_artifact_registry_repository.agent_images.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
}

resource "google_network_services_agent_gateway" "egress" {
  provider = google-nightly

  project     = var.project_id
  location    = var.location
  name        = var.gateway_name
  description = "20260822 default-deny Agent-to-Anywhere gateway; GitHub endpoint is allowlisted by registry IAM."
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
    google_project_service.services["agentregistry.googleapis.com"],
    google_project_service.services["networkservices.googleapis.com"],
    google_project_service.services["networksecurity.googleapis.com"],
  ]
}

resource "google_network_services_authz_extension" "iap" {
  provider = google-nightly

  project   = var.project_id
  location  = var.location
  name      = "agw-20260822-iap-authz"
  service   = "iap.googleapis.com"
  fail_open = false
  timeout   = "1s"
  metadata = {
    iamEnforcementMode = "ENFORCE"
    iapPolicyVersion   = "V1"
  }

  depends_on = [google_project_service.services["networkservices.googleapis.com"]]
}

resource "google_network_security_authz_policy" "iap" {
  provider = google-nightly

  project        = var.project_id
  location       = var.location
  name           = "agw-20260822-iap-policy"
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
