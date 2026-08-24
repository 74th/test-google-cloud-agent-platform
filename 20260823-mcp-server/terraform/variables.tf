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
  description = "Existing Agent Gateway resource reused by this experiment."
  type        = string
  default     = "projects/nnyn-dev/locations/us-central1/agentGateways/agw-20260822-egress"

  validation {
    condition     = can(regex("^projects/[^/]+/locations/[^/]+/agentGateways/[^/]+$", var.agent_gateway_id))
    error_message = "agent_gateway_id must be a fully qualified Agent Gateway resource name."
  }
}

variable "agent_gateway_name" {
  description = "Dedicated Agent Gateway resource name."
  type        = string
  default     = "mcp-20260823-egress"
}

variable "cloud_run_registry_service_id" {
  description = "Stable Registry Service ID for the Cloud Run MCP endpoint."
  type        = string
  default     = "mcp-20260823-cloud-run"
}

variable "gke_registry_service_id" {
  description = "Stable Registry Service ID for the GKE MCP endpoint."
  type        = string
  default     = "mcp-20260823-gke"
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

variable "gke_auth_audience" {
  description = "Exact authentication audience configured for the GKE front door."
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
