resource "google_container_cluster" "sandbox" {
  project                     = var.project_id
  name                        = local.cluster_name
  location                    = var.region
  network                     = google_compute_network.sandbox.id
  subnetwork                  = google_compute_subnetwork.sandbox.id
  networking_mode             = "VPC_NATIVE"
  datapath_provider           = "ADVANCED_DATAPATH"
  enable_fqdn_network_policy  = true
  enable_intranode_visibility = true
  deletion_protection         = false

  remove_default_node_pool = true
  initial_node_count       = 1
  release_channel {
    channel = "REGULAR"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = local.pods_range_name
    services_secondary_range_name = local.services_range_name
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = var.control_plane_cidr
  }

  master_authorized_networks_config {
    gcp_public_cidrs_access_enabled = false
    dynamic "cidr_blocks" {
      for_each = var.authorized_control_plane_cidrs
      content {
        cidr_block   = cidrhost(cidr_blocks.value.cidr_block, 0) == cidr_blocks.value.cidr_block ? cidr_blocks.value.cidr_block : cidr_blocks.value.cidr_block
        display_name = cidr_blocks.value.display_name
      }
    }
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  addons_config {
    gce_persistent_disk_csi_driver_config {
      enabled = true
    }
    dns_cache_config {
      enabled = true
    }
  }

  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }

  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS"]
  }

  depends_on = [
    google_project_service.required,
    google_compute_router_nat.sandbox,
  ]
}

resource "google_container_node_pool" "system" {
  project    = var.project_id
  name       = local.system_pool_name
  location   = var.region
  cluster    = google_container_cluster.sandbox.name
  node_count = var.system_node_count

  node_config {
    machine_type    = var.system_machine_type
    service_account = google_service_account.nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    disk_type       = "pd-balanced"
    disk_size_gb    = 100
    labels = {
      "research-gke-agent-sandbox/pool" = "system"
    }
    workload_metadata_config {
      mode = "GKE_METADATA"
    }
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

resource "google_container_node_pool" "gvisor" {
  project    = var.project_id
  name       = local.gvisor_pool_name
  location   = var.region
  cluster    = google_container_cluster.sandbox.name
  node_count = var.gvisor_node_count

  node_config {
    machine_type    = var.gvisor_machine_type
    service_account = google_service_account.nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    disk_type       = "pd-balanced"
    disk_size_gb    = var.gvisor_node_disk_gb
    labels = {
      "research-gke-agent-sandbox/pool" = "gvisor"
    }
    workload_metadata_config {
      mode = "GKE_METADATA"
    }
    sandbox_config {
      type = "GVISOR"
    }
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
}
