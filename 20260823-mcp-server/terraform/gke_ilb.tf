resource "google_compute_address" "gke_internal_https" {
  count        = var.enable_gke ? 1 : 0
  name         = "${var.name_prefix}-gke-ilb"
  project      = var.project_id
  region       = var.region
  address_type = "INTERNAL"
  subnetwork   = google_compute_subnetwork.mcp[0].id
  purpose      = "GCE_ENDPOINT"

  lifecycle {
    precondition {
      condition     = var.gke_mcp_hostname == "gke.mcp-20260823.internal"
      error_message = "The private GKE front door must use the reviewed consumer hostname."
    }
  }
}

# Gateway API regional internal Application Load Balancers require a VIP that
# is reserved for load-balancer sharing. Keep the existing Ingress VIP above
# intact while the Gateway API path is brought up for comparison.
resource "google_compute_address" "gke_gateway" {
  count        = var.enable_gke ? 1 : 0
  name         = "${var.name_prefix}-gke-gateway-vip"
  project      = var.project_id
  region       = var.region
  address_type = "INTERNAL"
  subnetwork   = google_compute_subnetwork.mcp[0].id
  purpose      = "SHARED_LOADBALANCER_VIP"

  lifecycle {
    precondition {
      condition     = var.gke_mcp_hostname == "gke.mcp-20260823.internal"
      error_message = "The private GKE Gateway must use the reviewed consumer hostname."
    }
  }
}

resource "google_compute_subnetwork" "gke_proxy_only" {
  count         = var.enable_gke ? 1 : 0
  name          = "${var.name_prefix}-proxy-only"
  project       = var.project_id
  region        = var.region
  network       = data.google_compute_network.agent_gateway.id
  ip_cidr_range = var.gke_proxy_only_cidr
  purpose       = "REGIONAL_MANAGED_PROXY"
  role          = "ACTIVE"
}

resource "google_dns_managed_zone" "gke_private" {
  count       = var.enable_gke ? 1 : 0
  name        = "${var.name_prefix}-private"
  project     = var.project_id
  dns_name    = "mcp-20260823.internal."
  description = "Consumer-owned private DNS for the internal GKE MCP front door."
  visibility  = "private"

  private_visibility_config {
    networks {
      network_url = data.google_compute_network.agent_gateway.id
    }
  }
}

resource "google_dns_record_set" "gke_mcp" {
  count        = var.enable_gke ? 1 : 0
  name         = "${var.gke_mcp_hostname}."
  project      = var.project_id
  managed_zone = google_dns_managed_zone.gke_private[0].name
  type         = "A"
  ttl          = 30
  rrdatas = [
    var.enable_gateway_api_https_probe
    ? google_compute_address.gke_gateway[0].address
    : google_compute_address.gke_internal_https[0].address
  ]
}

resource "google_dns_record_set" "gke_gateway_diagnostic" {
  count        = var.enable_gke ? 1 : 0
  name         = "${var.gke_gateway_diagnostic_hostname}."
  project      = var.project_id
  managed_zone = google_dns_managed_zone.gke_private[0].name
  type         = "A"
  ttl          = 30
  rrdatas      = [google_compute_address.gke_gateway[0].address]
}
