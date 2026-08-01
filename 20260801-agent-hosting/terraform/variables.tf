variable "project_id" {
  description = "Google Cloud project that hosts the agent."
  type        = string
  default     = "nnyn-dev"
}

variable "location" {
  description = "Primary Agent Platform region."
  type        = string
  default     = "us-central1"
}
