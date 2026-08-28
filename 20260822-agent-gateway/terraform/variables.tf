variable "project_id" {
  description = "Google Cloud project hosting the validation resources."
  type        = string
  default     = "nnyn-dev"
  validation {
    condition     = var.project_id == "nnyn-dev"
    error_message = "This validation is intentionally scoped to project nnyn-dev."
  }
}

variable "location" {
  description = "Agent Runtime and Agent Gateway region."
  type        = string
  default     = "us-central1"
  validation {
    condition     = var.location == "us-central1"
    error_message = "This validation is intentionally scoped to us-central1."
  }
}

variable "agent_gateway_id" {
  description = "Required full common/terraform agent_gateway_id handoff."
  type        = string
  nullable    = false

  validation {
    condition = can(regex(
      "^projects/nnyn-dev/locations/us-central1/agentGateways/[a-z][a-z0-9-]{0,62}[a-z0-9]$",
      var.agent_gateway_id,
    ))
    error_message = "agent_gateway_id must be a full nnyn-dev/us-central1 Agent Gateway resource name."
  }
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

variable "runtime_image_uri" {
  description = "Container image URI for the Agent Runtime."
  type        = string
  default     = "us-central1-docker.pkg.dev/nnyn-dev/agent-gateway-20260828/claude-agent-gateway@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.runtime_image_uri))
    error_message = "runtime_image_uri must be an immutable Artifact Registry image digest."
  }
}

variable "display_name" {
  description = "Consumer-owned Runtime display name."
  type        = string
  default     = "agent-gateway-20260828-claude"
}

variable "labels" {
  description = "Labels used to scope cleanup to this validation."
  type        = map(string)
  default = {
    validation = "20260822-agent-gateway"
    managed_by = "terraform"
  }
}
