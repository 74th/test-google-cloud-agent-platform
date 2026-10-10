resource "google_compute_network" "sandbox" {
  project                 = var.project_id
  name                    = local.vpc_name
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
  depends_on              = [google_project_service.required]
}

resource "google_compute_subnetwork" "sandbox" {
  project                  = var.project_id
  name                     = local.subnet_name
  region                   = var.region
  network                  = google_compute_network.sandbox.id
  ip_cidr_range            = var.network_cidr
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = local.pods_range_name
    ip_cidr_range = var.pods_cidr
  }

  secondary_ip_range {
    range_name    = local.services_range_name
    ip_cidr_range = var.services_cidr
  }
}

resource "google_compute_router" "sandbox" {
  project = var.project_id
  name    = local.router_name
  region  = var.region
  network = google_compute_network.sandbox.id
}

resource "google_compute_router_nat" "sandbox" {
  project                            = var.project_id
  name                               = local.nat_name
  router                             = google_compute_router.sandbox.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = google_compute_subnetwork.sandbox.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
