variable "project_id" {
  description = "Google Cloud project hosting the isolated validation resources."
  type        = string
  default     = "nnyn-dev"
}

variable "region" {
  description = "Cloud Run, Artifact Registry, and GKE region."
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "Zonal location for the optional GKE Standard cluster."
  type        = string
  default     = "us-central1-a"
}

variable "name_prefix" {
  description = "Collision-resistant name prefix used by every experiment resource."
  type        = string
  default     = "mcp-20260823-mcp-server"
}

variable "experiment_label" {
  description = "Stable identifier included in labels where a name has a provider limit."
  type        = string
  default     = "20260823-mcp-server"
}

variable "container_image" {
  description = "Immutable Artifact Registry image reference, including a sha256 digest."
  type        = string
  default     = "us-central1-docker.pkg.dev/nnyn-dev/mcp-20260823-mcp-server/mcp-server@sha256:0000000000000000000000000000000000000000000000000000000000000000"

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.container_image))
    error_message = "container_image must end in an immutable @sha256:<64 hex digits> digest."
  }
}

variable "enable_gke" {
  description = "Create the dedicated GKE Standard phase. Keep false for the Cloud Run phase."
  type        = bool
  default     = false
}

variable "node_cidr" {
  description = "Dedicated primary subnet range; verified against the project inventory."
  type        = string
  default     = "10.240.0.0/20"
}

variable "pod_cidr" {
  description = "Dedicated GKE Pod secondary range."
  type        = string
  default     = "10.241.0.0/16"
}

variable "service_cidr" {
  description = "Dedicated GKE Service secondary range."
  type        = string
  default     = "10.242.0.0/20"
}
