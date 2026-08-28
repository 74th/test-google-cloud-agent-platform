terraform {
  required_version = ">= 1.8.0"

  backend "local" {
    path = "terraform.tfstate"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.45.0"
    }
    google-nightly = {
      source  = "hashicorp/google-nightly"
      version = "2026.4.8-7.27.0"
    }
  }
}
