locals {
  required_services = toset([
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "container.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "iap.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
  ])
}

resource "google_artifact_registry_repository" "agent_runtime" {
  project       = var.project_id
  location      = var.region
  repository_id = "${var.name_prefix}-agent"
  description   = "20260823-mcp-server Agent Runtime image repository"
  format        = "DOCKER"
  labels        = local.common_labels

  depends_on = [google_project_service.required]
}

resource "google_project_service" "required" {
  for_each           = local.required_services
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "mcp" {
  project       = var.project_id
  location      = var.region
  repository_id = local.artifact_repository
  description   = "20260823-mcp-server validation images"
  format        = "DOCKER"
  labels        = local.common_labels

  depends_on = [google_project_service.required]
}
