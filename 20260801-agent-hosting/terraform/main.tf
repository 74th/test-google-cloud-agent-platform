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

resource "google_project_service" "vertex_ai" {
  project            = var.project_id
  service            = "aiplatform.googleapis.com"
  disable_on_destroy = false
}

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "claude-agent-runtime"
  display_name = "2026-08-01 20260801-agent-hosting test runtime"
  description  = "Test-only identity for the 2026-08-01 20260801-agent-hosting Agent Platform Claude Agent SDK container."
}

resource "google_project_iam_member" "runtime_agent_platform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}
