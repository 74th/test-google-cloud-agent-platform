variable "project_id" {
  description = "Google Cloud project that owns the shared Agent Gateway infrastructure."
  type        = string
  default     = "nnyn-dev"

  validation {
    condition     = var.project_id == "nnyn-dev"
    error_message = "This experiment is intentionally scoped to project nnyn-dev."
  }
}

variable "region" {
  description = "Region for the shared subnet, network attachment, and Agent Gateway."
  type        = string
  default     = "us-central1"

  validation {
    condition     = var.region == "us-central1"
    error_message = "This experiment is intentionally scoped to us-central1."
  }
}

variable "network_name" {
  description = "Name of the dedicated shared Agent Gateway VPC."
  type        = string
  default     = "common-agent-gateway-vpc"
}

variable "subnetwork_name" {
  description = "Name of the dedicated PSC interface subnet."
  type        = string
  default     = "common-agent-gateway-subnet"
}

variable "subnetwork_cidr" {
  description = "Dedicated /28 range used by the Agent Gateway PSC interface network attachment."
  type        = string
  default     = "10.243.0.0/28"

  validation {
    condition     = can(cidrhost(var.subnetwork_cidr, 1)) && split("/", var.subnetwork_cidr)[1] == "28"
    error_message = "subnetwork_cidr must be a valid IPv4 /28 CIDR."
  }
}

variable "network_attachment_name" {
  description = "Name of the PSC interface Network Attachment used by Agent Gateway."
  type        = string
  default     = "common-agent-gateway-attachment"
}

variable "agent_gateway_name" {
  description = "Name of the shared Agent-to-Anywhere Agent Gateway."
  type        = string
  default     = "common-agent-gateway-egress"
}

variable "labels" {
  description = "Labels applied to resources that support labels."
  type        = map(string)
  default = {
    environment = "experiment"
    managed_by  = "terraform"
    owner       = "common"
  }
}
