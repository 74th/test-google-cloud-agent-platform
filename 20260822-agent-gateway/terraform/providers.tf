provider "google" {
  project = var.project_id
  region  = var.location
}

provider "google-beta" {
  project = var.project_id
  region  = var.location
}

provider "google-nightly" {
  project = var.project_id
  region  = var.location
}
