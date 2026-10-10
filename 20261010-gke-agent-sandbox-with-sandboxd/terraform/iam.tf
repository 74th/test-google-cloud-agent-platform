resource "google_service_account" "nodes" {
  project      = var.project_id
  account_id   = local.node_service_account
  display_name = "${var.name_prefix} GKE node identity"
  description  = "Node identity for the isolated GKE Agent Sandbox research environment."
  depends_on   = [google_project_service.required]
}

resource "google_project_iam_member" "node_roles" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/monitoring.viewer",
    "roles/artifactregistry.reader",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.nodes.email}"
}
