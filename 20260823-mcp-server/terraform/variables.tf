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

variable "gke_network_name" {
  description = "Existing VPC used by the common Agent Gateway Network Attachment. The consumer adds only its own subnet."
  type        = string
  default     = "common-agent-gateway-vpc"

  validation {
    condition     = var.gke_network_name == "common-agent-gateway-vpc"
    error_message = "gke_network_name must be the reviewed common-agent-gateway-vpc; do not create or use an unrelated VPC."
  }
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

variable "gke_proxy_only_cidr" {
  description = "Consumer-owned proxy-only range required by the regional internal HTTPS Load Balancer."
  type        = string
  default     = "10.244.0.0/23"
}

variable "gke_service_cluster_ip" {
  description = "Reserved ClusterIP used by the first private DNS/HTTPS reachability probe; avoid GKE system Services."
  type        = string
  default     = "10.242.0.20"

  validation {
    condition     = can(cidrhost(var.service_cidr, 0)) && can(regex("^10\\.242\\.[0-9]+\\.[0-9]+$", var.gke_service_cluster_ip))
    error_message = "gke_service_cluster_ip must be an address in the dedicated 10.242 service range."
  }
}

variable "agent_runtime_image" {
  description = "Immutable Agent Runtime image reference, including a sha256 digest."
  type        = string
  default     = "us-central1-docker.pkg.dev/nnyn-dev/mcp-20260823-mcp-server-agent/agent-runtime@sha256:0000000000000000000000000000000000000000000000000000000000000000"

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.agent_runtime_image))
    error_message = "agent_runtime_image must end in an immutable @sha256:<64 hex digits> digest."
  }
}

variable "agent_runtime_name" {
  description = "Dedicated Agent Runtime display/resource name."
  type        = string
  default     = "mcp-20260823-runtime"
}

variable "agent_gateway_id" {
  description = "Shared Agent Gateway resource ID supplied explicitly from common output."
  type        = string

  validation {
    condition     = var.agent_gateway_id == "projects/nnyn-dev/locations/us-central1/agentGateways/common-egress"
    error_message = "agent_gateway_id must be the reviewed common-egress resource from common/terraform output."
  }
}

variable "cloud_run_registry_service_id" {
  description = "Stable Registry Service ID for the Cloud Run MCP endpoint."
  type        = string
  default     = "mcp-20260823-cloud-run"

  validation {
    condition     = can(regex("^mcp-20260823-[a-z0-9-]+$", var.cloud_run_registry_service_id))
    error_message = "cloud_run_registry_service_id must be a collision-resistant 20260823 consumer ID."
  }
}

variable "gke_registry_service_id" {
  description = "Stable Registry Service ID for the GKE MCP endpoint."
  type        = string
  default     = "mcp-20260823-gke"

  validation {
    condition     = can(regex("^mcp-20260823-[a-z0-9-]+$", var.gke_registry_service_id))
    error_message = "gke_registry_service_id must be a collision-resistant 20260823 consumer ID."
  }
}

variable "gke_http_diagnostic_registry_service_id" {
  description = "Stable Registry Service ID for the explicit private HTTP Gateway API routing diagnostic."
  type        = string
  default     = "mcp-20260823-gke-http-diagnostic"

  validation {
    condition     = can(regex("^mcp-20260823-[a-z0-9-]+$", var.gke_http_diagnostic_registry_service_id))
    error_message = "gke_http_diagnostic_registry_service_id must be a collision-resistant 20260823 consumer ID."
  }
}

variable "cloud_run_auth_audience" {
  description = "Exact Cloud Run ID-token audience; defaults to the created service URI."
  type        = string
  default     = ""
}

variable "gke_mcp_hostname" {
  description = "Operator-authorized DNS hostname for the authenticated GKE HTTPS front door. Required for enable_gke."
  type        = string
  default     = ""

  validation {
    condition     = var.gke_mcp_hostname == "" || can(regex("^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\\.[a-z]{2,}$", var.gke_mcp_hostname))
    error_message = "gke_mcp_hostname must be a DNS hostname, or empty only while enable_gke=false."
  }
}

variable "gke_gateway_diagnostic_hostname" {
  description = "Private DNS hostname used only by the unauthenticated Gateway API HTTP routing diagnostic."
  type        = string
  default     = "gke-gateway-http.mcp-20260823.internal"

  validation {
    condition     = can(regex("^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\\.[a-z]{2,}$", var.gke_gateway_diagnostic_hostname))
    error_message = "gke_gateway_diagnostic_hostname must be a DNS hostname."
  }
}

variable "enable_gateway_api_https_probe" {
  description = "Temporarily point the consumer GKE hostname at the Gateway API HTTPS VIP for a bounded common-egress diagnostic. The Gateway certificate remains an out-of-band test certificate."
  type        = bool
  default     = false
}

variable "gke_auth_audience" {
  description = "Exact authentication audience configured for the GKE front door."
  type        = string
  default     = ""
}

variable "gke_http_diagnostic_auth_audience" {
  description = "Exact audience used for the explicit private HTTP diagnostic request; it is not endpoint authorization."
  type        = string
  default     = ""
}

variable "use_mcp_caller_service_account" {
  description = "Use a dedicated keyless caller SA when direct Agent Identity token minting is unavailable."
  type        = bool
  default     = true
}

variable "vertex_project_id" {
  description = "Project used by the Vertex Claude integration."
  type        = string
  default     = "nnyn-dev"
}

variable "vertex_region" {
  description = "Vertex Claude model region."
  type        = string
  default     = "global"
}
