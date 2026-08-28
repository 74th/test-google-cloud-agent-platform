terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}

locals {
  common_labels = merge(var.labels, { project = "agent-gateway-egress-consumer" })
}

resource "google_project_service" "services" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "agentregistry.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
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
  repository_id = "agent-gateway-20260828"
  description   = "20260828 consumer-owned BYOC validation images."
  format        = "DOCKER"
  labels        = local.common_labels

  depends_on = [google_project_service.services["artifactregistry.googleapis.com"]]
}

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "agent-gateway-20260828-runtime"
  display_name = "20260828 shared Gateway validation runtime"
  description  = "Consumer-owned identity for the shared Agent Gateway validation Runtime."
}

resource "google_project_iam_member" "runtime_platform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_service_usage_consumer" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}
