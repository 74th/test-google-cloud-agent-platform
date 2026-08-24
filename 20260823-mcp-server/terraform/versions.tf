terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 7.45.0, < 8.0.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 7.45.0, < 8.0.0"
    }
    google-nightly = {
      source  = "hashicorp/google-nightly"
      version = "2026.4.8-7.27.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

provider "google-nightly" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}
