terraform {
  required_version = ">= 1.8.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 7.20.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 7.20.0"
    }
    google-nightly = {
      source  = "hashicorp/google-nightly"
      version = "2026.4.8-7.27.0"
    }
  }
}
