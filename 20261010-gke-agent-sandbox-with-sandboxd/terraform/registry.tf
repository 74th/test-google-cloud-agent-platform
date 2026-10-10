resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = local.registry_name
  description   = "Container images for ${var.name_prefix}."
  format        = "DOCKER"

  cleanup_policy_dry_run = true
  depends_on             = [google_project_service.required]
}
