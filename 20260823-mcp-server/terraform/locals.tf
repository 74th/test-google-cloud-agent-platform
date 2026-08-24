locals {
  common_labels = {
    experiment = var.experiment_label
    managed_by = "terraform"
  }

  artifact_repository = var.name_prefix
  container_image     = var.container_image
  agent_runtime_image = var.agent_runtime_image
  agent_gateway_id    = var.agent_gateway_id
  registry_path       = "//agentregistry.googleapis.com/projects/${var.project_id}/locations/${var.region}"
  tool_spec_content   = file("${path.module}/../toolspec.json")
}
