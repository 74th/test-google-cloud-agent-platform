resource "google_service_account" "cloud_run_runtime" {
  account_id   = "${var.name_prefix}-run"
  display_name = "20260823-mcp-server Cloud Run runtime"
  project      = var.project_id
}

resource "google_service_account" "test_invoker" {
  account_id   = "mcp-20260823-invoker"
  display_name = "20260823-mcp-server test invoker"
  project      = var.project_id
}

resource "google_service_account" "gke_node" {
  count        = var.enable_gke ? 1 : 0
  account_id   = "mcp-20260823-gke-node"
  display_name = "20260823-mcp-server GKE node runtime"
  project      = var.project_id
}

resource "google_service_account" "gke_workload" {
  count        = var.enable_gke ? 1 : 0
  account_id   = "mcp-20260823-gke-workload"
  display_name = "20260823-mcp-server GKE MCP workload"
  project      = var.project_id
}

resource "google_project_iam_member" "cloud_run_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cloud_run_runtime.email}"
}

resource "google_project_iam_member" "gke_node_logs" {
  count   = var.enable_gke ? 1 : 0
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.gke_node[0].email}"
}

resource "google_project_iam_member" "gke_node_metrics" {
  count   = var.enable_gke ? 1 : 0
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.gke_node[0].email}"
}

resource "google_project_iam_member" "gke_node_artifacts" {
  count   = var.enable_gke ? 1 : 0
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.gke_node[0].email}"
}
