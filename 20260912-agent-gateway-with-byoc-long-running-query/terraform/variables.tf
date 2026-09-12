variable "project_id" {
  description = "Google Cloud project hosting this self-contained repro (self-contained, no cross-project dependency)."
  type        = string
  default     = "dev-74th-20260912"
}

variable "region" {
  description = "Region for the VPC, Agent Gateway, Runtime, and query-job bucket."
  type        = string
  default     = "us-central1"
}

variable "network_name" {
  type    = string
  default = "byoc20260912-agent-gateway-vpc"
}

variable "subnetwork_name" {
  type    = string
  default = "byoc20260912-agent-gateway-subnet"
}

variable "subnetwork_cidr" {
  description = "Dedicated /28 range for the Agent Gateway PSC interface network attachment."
  type        = string
  default     = "10.244.0.0/28"

  validation {
    condition     = can(cidrhost(var.subnetwork_cidr, 1)) && split("/", var.subnetwork_cidr)[1] == "28"
    error_message = "subnetwork_cidr must be a valid IPv4 /28 CIDR."
  }
}

variable "network_attachment_name" {
  type    = string
  default = "byoc20260912-agent-gateway-attachment"
}

variable "agent_gateway_name" {
  description = "Name of this repro's own Agent-to-Anywhere Agent Gateway (not the shared common-egress gateway)."
  type        = string
  default     = "byoc20260912-egress"
}

variable "github_registry_service_id" {
  description = "Agent Registry Service that allow-lists https://github.com through the Gateway. https://www.tohoho-web.com is intentionally NOT registered, to demonstrate default-deny."
  type        = string
  default     = "byoc20260912-github-allow"
}

variable "artifact_registry_repository_id" {
  type    = string
  default = "byoc20260912-images"
}

variable "query_job_bucket_name" {
  description = "GCS bucket used for run_query_job input/output objects."
  type        = string
  default     = "dev-74th-20260912-byoc-queryjobs"
}

variable "runtime_image_uri" {
  description = "Container image URI for both Runtimes. Must be an immutable Artifact Registry digest."
  type        = string
  default     = "us-central1-docker.pkg.dev/dev-74th-20260912/byoc20260912-images/byoc-gateway-longrunning@sha256:0000000000000000000000000000000000000000000000000000000000000000"

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.runtime_image_uri))
    error_message = "runtime_image_uri must be an immutable Artifact Registry image digest."
  }
}

variable "no_gateway_display_name" {
  description = "Display name of the Runtime with no Agent Gateway association (test case 1: works)."
  type        = string
  default     = "byoc20260912-no-gateway"
}

variable "gateway_display_name" {
  description = "Display name of the Runtime associated with this repro's Agent Gateway (test cases 2 and 3)."
  type        = string
  default     = "byoc20260912-gateway"
}

variable "labels" {
  type = map(string)
  default = {
    validation = "byoc20260912-agent-gateway-with-byoc-long-running-query"
    managed_by = "terraform"
  }
}
