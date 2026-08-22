variable "project_id" {
  description = "Google Cloud project hosting the validation resources."
  type        = string
  default     = "nnyn-dev"
}

variable "location" {
  description = "Agent Runtime and Agent Gateway region."
  type        = string
  default     = "us-central1"
}

variable "vertex_project_id" {
  description = "Project used by Claude Vertex AI authentication."
  type        = string
  default     = "nnyn-dev"
}

variable "vertex_region" {
  description = "Vertex AI region for Claude Model Garden inference."
  type        = string
  default     = "global"
}

variable "gateway_name" {
  description = "Unique Agent Gateway name for this validation."
  type        = string
  default     = "agw-20260822-egress"
}

variable "labels" {
  description = "Labels used to scope cleanup to this validation."
  type        = map(string)
  default = {
    validation = "20260822-agent-gateway"
    managed_by = "terraform"
  }
}
