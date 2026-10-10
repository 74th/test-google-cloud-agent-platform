variable "project_id" {
  description = "Explicit Google Cloud project that owns this isolated environment."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a valid Google Cloud project ID."
  }
}

variable "region" {
  description = "Region for the GKE cluster and supporting resources."
  type        = string
  default     = "us-central1"
}

variable "name_prefix" {
  description = "Long research prefix used where the target API permits it."
  type        = string
  default     = "research-gke-agent-sandbox-with-sandboxd"

  validation {
    condition     = length(var.name_prefix) <= 40 && can(regex("^[a-z][a-z0-9-]*[a-z0-9]$", var.name_prefix))
    error_message = "name_prefix must be lowercase alphanumeric/hyphen and at most 40 characters."
  }
}

variable "short_name_prefix" {
  description = "Deterministic short prefix for resources with strict name limits."
  type        = string
  default     = "research-gke-as-sbd"

  validation {
    condition     = length(var.short_name_prefix) <= 20 && can(regex("^[a-z][a-z0-9-]*[a-z0-9]$", var.short_name_prefix))
    error_message = "short_name_prefix must be lowercase alphanumeric/hyphen and at most 20 characters."
  }
}

variable "network_cidr" {
  description = "Primary subnet range; must not overlap any existing VPC range in the project."
  type        = string
  default     = "192.168.0.0/20"
  validation {
    condition     = can(cidrnetmask(var.network_cidr))
    error_message = "network_cidr must be a valid IPv4 CIDR."
  }
}

variable "pods_cidr" {
  description = "GKE Pod secondary range; must not overlap any existing project range."
  type        = string
  default     = "192.168.32.0/19"
  validation {
    condition     = can(cidrnetmask(var.pods_cidr))
    error_message = "pods_cidr must be a valid IPv4 CIDR."
  }
}

variable "services_cidr" {
  description = "GKE Service secondary range; must not overlap any existing project range."
  type        = string
  default     = "192.168.64.0/20"
  validation {
    condition     = can(cidrnetmask(var.services_cidr))
    error_message = "services_cidr must be a valid IPv4 CIDR."
  }
}

variable "control_plane_cidr" {
  description = "Private /28 range reserved for the GKE control plane."
  type        = string
  default     = "172.20.0.0/28"
  validation {
    condition     = can(cidrnetmask(var.control_plane_cidr)) && tonumber(split("/", var.control_plane_cidr)[1]) == 28
    error_message = "control_plane_cidr must be a valid IPv4 /28 CIDR."
  }
}

variable "authorized_control_plane_cidrs" {
  description = "Caller-owned public IPv4 CIDRs allowed to access the GKE control-plane endpoint. Supply explicitly in tfvars."
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  default = []
  validation {
    condition     = alltrue([for entry in var.authorized_control_plane_cidrs : can(cidrnetmask(entry.cidr_block))])
    error_message = "Every authorized control-plane entry must contain a valid IPv4 CIDR."
  }
}

variable "system_machine_type" {
  description = "Machine type for controller and management workloads."
  type        = string
  default     = "e2-standard-2"
}

variable "gvisor_machine_type" {
  description = "Machine type for gVisor sandbox workloads."
  type        = string
  default     = "e2-standard-2"
}

variable "system_node_count" {
  description = "Initial node count for the regular system node pool."
  type        = number
  default     = 1
  validation {
    condition     = var.system_node_count >= 1 && var.system_node_count <= 10
    error_message = "system_node_count must be between 1 and 10."
  }
}

variable "gvisor_node_count" {
  description = "Initial node count for the gVisor node pool."
  type        = number
  default     = 1
  validation {
    condition     = var.gvisor_node_count >= 1 && var.gvisor_node_count <= 10
    error_message = "gvisor_node_count must be between 1 and 10."
  }
}

variable "gvisor_node_disk_gb" {
  description = "Boot disk size for gVisor nodes, in GiB."
  type        = number
  default     = 100
  validation {
    condition     = var.gvisor_node_disk_gb >= 30 && var.gvisor_node_disk_gb <= 1000
    error_message = "gvisor_node_disk_gb must be between 30 and 1000."
  }
}
