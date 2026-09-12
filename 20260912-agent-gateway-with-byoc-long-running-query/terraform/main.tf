locals {
  registry_path  = "//agentregistry.googleapis.com/projects/${var.project_id}/locations/${var.region}"
  common_labels  = merge(var.labels, { project = "20260912-agent-gateway-with-byoc-long-running-query" })
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_project_service" "required" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "agentregistry.googleapis.com",
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iap.googleapis.com",
    "logging.googleapis.com",
    "networksecurity.googleapis.com",
    "networkservices.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# --- Self-contained network path for the Agent Gateway PSC interface -------

resource "google_compute_network" "agent_gateway" {
  project                 = var.project_id
  name                    = var.network_name
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"

  depends_on = [google_project_service.required["compute.googleapis.com"]]
}

resource "google_compute_subnetwork" "agent_gateway" {
  project       = var.project_id
  region        = var.region
  name          = var.subnetwork_name
  network       = google_compute_network.agent_gateway.id
  ip_cidr_range = var.subnetwork_cidr
  purpose       = "PRIVATE"
}

resource "google_compute_network_attachment" "agent_gateway" {
  project               = var.project_id
  region                = var.region
  name                  = var.network_attachment_name
  description           = "Dedicated PSC interface attachment for the 20260912 repro Agent Gateway."
  connection_preference = "ACCEPT_AUTOMATIC"
  subnetworks           = [google_compute_subnetwork.agent_gateway.self_link]
}

# --- Agent Gateway (this repro's own gateway; not the shared common-egress) -

resource "google_network_services_agent_gateway" "repro" {
  provider = google-nightly

  project     = var.project_id
  location    = var.region
  name        = var.agent_gateway_name
  description = "Agent-to-Anywhere gateway isolated to the 20260912 BYOC long-running query repro."
  labels      = var.labels
  protocols   = ["MCP"]
  registries  = [local.registry_path]

  google_managed {
    governed_access_path = "AGENT_TO_ANYWHERE"
  }

  network_config {
    egress {
      network_attachment = google_compute_network_attachment.agent_gateway.self_link
    }
  }

  timeouts {
    create = "30m"
    update = "30m"
    delete = "30m"
  }

  depends_on = [
    google_project_service.required["agentregistry.googleapis.com"],
    google_project_service.required["networkservices.googleapis.com"],
  ]
}

# Fail-closed IAP enforcement, mirroring the shared common-egress gateway.
resource "google_network_services_authz_extension" "iap" {
  provider = google-nightly

  project   = var.project_id
  location  = var.region
  name      = "byoc20260912-egress-iap-authz"
  service   = "iap.googleapis.com"
  fail_open = false
  timeout   = "1s"
  metadata = {
    iamEnforcementMode = "ENFORCE"
    iapPolicyVersion   = "V1"
  }

  depends_on = [google_project_service.required["networkservices.googleapis.com"]]
}

resource "google_network_security_authz_policy" "iap" {
  provider = google-nightly

  project        = var.project_id
  location       = var.region
  name           = "byoc20260912-egress-iap-policy"
  policy_profile = "REQUEST_AUTHZ"
  action         = "CUSTOM"

  target {
    resources = [google_network_services_agent_gateway.repro.id]
  }

  custom_provider {
    authz_extension {
      resources = [google_network_services_authz_extension.iap.id]
    }
  }

  depends_on = [google_project_service.required["networksecurity.googleapis.com"]]
}

# --- Registry: allow only github.com, so tohoho-web.com is default-denied --

resource "google_agent_registry_service" "github" {
  provider = google-nightly

  project      = var.project_id
  location     = var.region
  service_id   = var.github_registry_service_id
  display_name = "20260912 repro GitHub allow endpoint"

  endpoint_spec {
    type = "NO_SPEC"
  }

  interfaces {
    url              = "https://github.com"
    protocol_binding = "HTTP_JSON"
  }
}

data "google_agent_registry_endpoint" "github" {
  provider = google-nightly

  project  = var.project_id
  location = var.region
  filter   = "displayName=\"20260912 repro GitHub allow endpoint\""

  depends_on = [google_agent_registry_service.github]
}

# --- Artifact Registry for the BYOC image ----------------------------------

resource "google_artifact_registry_repository" "agent_images" {
  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_repository_id
  description   = "20260912 BYOC image: Agent Gateway + long-running query repro."
  format        = "DOCKER"
  labels        = local.common_labels

  depends_on = [google_project_service.required["artifactregistry.googleapis.com"]]
}

resource "google_artifact_registry_repository_iam_member" "agent_runtime_reader" {
  project    = var.project_id
  location   = google_artifact_registry_repository.agent_images.location
  repository = google_artifact_registry_repository.agent_images.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
}

# --- GCS bucket for run_query_job input/output objects ----------------------

resource "google_storage_bucket" "query_jobs" {
  project                     = var.project_id
  name                        = var.query_job_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
  labels                      = local.common_labels

  depends_on = [google_project_service.required["storage.googleapis.com"]]
}

resource "google_storage_bucket_iam_member" "query_job_reasoning_engine_agent" {
  bucket = google_storage_bucket.query_jobs.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
}
