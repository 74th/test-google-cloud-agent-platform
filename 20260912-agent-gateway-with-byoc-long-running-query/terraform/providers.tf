provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

provider "google-nightly" {
  project = var.project_id
  region  = var.region
}
