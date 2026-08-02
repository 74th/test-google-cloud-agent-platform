terraform {
  required_version = ">= 1.8.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.location
}

resource "google_project_service" "required" {
  for_each           = toset(["aiplatform.googleapis.com", "artifactregistry.googleapis.com", "storage.googleapis.com", "logging.googleapis.com"])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

data "google_project" "current" { project_id = var.project_id }

resource "google_artifact_registry_repository" "verification" {
  project       = var.project_id
  location      = var.location
  repository_id = "byoc-query-verification"
  format        = "DOCKER"
  description   = "Test-only BYOC query verification images"
  depends_on    = [google_project_service.required]
}

resource "google_storage_bucket" "query_jobs" {
  project                     = var.project_id
  name                        = var.query_job_bucket_name
  location                    = var.location
  uniform_bucket_level_access = true
  force_destroy               = false
}

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "byoc-query-runtime"
  display_name = "BYOC query verification runtime"
}

resource "google_project_iam_member" "runtime_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_storage_bucket_iam_member" "runtime_output" {
  bucket = google_storage_bucket.query_jobs.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_artifact_registry_repository_iam_member" "agent_runtime_reader" {
  project    = var.project_id
  location   = google_artifact_registry_repository.verification.location
  repository = google_artifact_registry_repository.verification.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
}
