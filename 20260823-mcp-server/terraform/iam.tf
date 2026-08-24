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

resource "google_service_account" "mcp_caller" {
  count        = var.use_mcp_caller_service_account ? 1 : 0
  account_id   = "${var.name_prefix}-caller"
  display_name = "20260823-mcp-server keyless MCP caller"
  project      = var.project_id
}

resource "google_artifact_registry_repository_iam_member" "agent_runtime_reader" {
  project    = var.project_id
  location   = google_artifact_registry_repository.agent_runtime.location
  repository = google_artifact_registry_repository.agent_runtime.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "registry_viewer" {
  project = var.project_id
  role    = "roles/agentregistry.viewer"
  member  = "principal://${google_vertex_ai_reasoning_engine.runtime.spec[0].effective_identity}"
}

resource "google_service_account_iam_member" "caller_token_creator" {
  count              = var.use_mcp_caller_service_account ? 1 : 0
  service_account_id = google_service_account.mcp_caller[0].name
  role               = "roles/iam.serviceAccountOpenIdTokenCreator"
  member             = "principal://${google_vertex_ai_reasoning_engine.runtime.spec[0].effective_identity}"
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
