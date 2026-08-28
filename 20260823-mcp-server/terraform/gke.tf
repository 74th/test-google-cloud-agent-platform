data "google_compute_network" "agent_gateway" {
  name    = var.gke_network_name
  project = var.project_id
}

resource "google_compute_subnetwork" "mcp" {
  count         = var.enable_gke ? 1 : 0
  name          = "${var.name_prefix}-subnet"
  project       = var.project_id
  region        = var.region
  network       = data.google_compute_network.agent_gateway.id
  ip_cidr_range = var.node_cidr

  secondary_ip_range {
    range_name    = "${var.name_prefix}-pods"
    ip_cidr_range = var.pod_cidr
  }

  secondary_ip_range {
    range_name    = "${var.name_prefix}-services"
    ip_cidr_range = var.service_cidr
  }
}

resource "google_container_cluster" "mcp" {
  count                    = var.enable_gke ? 1 : 0
  name                     = "${var.name_prefix}-gke"
  project                  = var.project_id
  location                 = var.zone
  network                  = data.google_compute_network.agent_gateway.name
  subnetwork               = google_compute_subnetwork.mcp[0].name
  remove_default_node_pool = true
  initial_node_count       = 1
  deletion_protection      = false

  ip_allocation_policy {
    cluster_secondary_range_name  = "${var.name_prefix}-pods"
    services_secondary_range_name = "${var.name_prefix}-services"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  release_channel {
    channel = "REGULAR"
  }

  resource_labels = local.common_labels
}

resource "google_container_node_pool" "mcp" {
  count      = var.enable_gke ? 1 : 0
  name       = "${var.name_prefix}-nodes"
  project    = var.project_id
  location   = var.zone
  cluster    = google_container_cluster.mcp[0].name
  node_count = 1

  node_config {
    machine_type    = "e2-small"
    service_account = google_service_account.gke_node[0].email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    labels          = local.common_labels
    tags            = ["${var.name_prefix}-gke"]
    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }
}

resource "google_service_account_iam_member" "gke_workload" {
  count              = var.enable_gke ? 1 : 0
  service_account_id = google_service_account.gke_workload[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[20260823-mcp-server/mcp-server]"
}
