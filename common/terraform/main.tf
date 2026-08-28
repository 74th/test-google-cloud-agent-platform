locals {
  registry_path = "//agentregistry.googleapis.com/projects/${var.project_id}/locations/${var.region}"
}

resource "google_project_service" "required" {
  for_each = toset([
    "agentregistry.googleapis.com",
    "compute.googleapis.com",
    "networkservices.googleapis.com",
    "serviceusage.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "agent_gateway" {
  project                 = var.project_id
  name                    = var.network_name
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"

  depends_on = [google_project_service.required["compute.googleapis.com"]]
}

resource "google_compute_subnetwork" "agent_gateway" {
  project       = var.project_id
  region        = var.region
  name          = var.subnetwork_name
  network       = google_compute_network.agent_gateway.id
  ip_cidr_range = var.subnetwork_cidr
  purpose       = "PRIVATE"
}

resource "google_compute_network_attachment" "agent_gateway" {
  project               = var.project_id
  region                = var.region
  name                  = var.network_attachment_name
  description           = "Dedicated PSC interface attachment for the common Agent Gateway."
  connection_preference = "ACCEPT_AUTOMATIC"
  subnetworks           = [google_compute_subnetwork.agent_gateway.self_link]
}

resource "google_network_services_agent_gateway" "shared" {
  provider = google-nightly

  project     = var.project_id
  location    = var.region
  name        = var.agent_gateway_name
  description = "Shared VPC-connected Agent-to-Anywhere gateway for isolated experiments."
  labels      = var.labels
  protocols   = ["MCP"]
  registries  = [local.registry_path]

  google_managed {
    governed_access_path = "AGENT_TO_ANYWHERE"
  }

  network_config {
    egress {
      network_attachment = google_compute_network_attachment.agent_gateway.self_link
    }
  }

  timeouts {
    create = "30m"
    update = "30m"
    delete = "30m"
  }

  depends_on = [
    google_project_service.required["agentregistry.googleapis.com"],
    google_project_service.required["networkservices.googleapis.com"],
  ]
}
