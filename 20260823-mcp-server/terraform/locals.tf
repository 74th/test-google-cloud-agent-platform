locals {
  common_labels = {
    experiment = var.experiment_label
    managed_by = "terraform"
  }

  artifact_repository = var.name_prefix
  container_image     = var.container_image
}
