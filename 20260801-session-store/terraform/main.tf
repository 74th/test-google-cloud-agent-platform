provider "google" {
  project = var.project_id
  region  = var.region
}

# Session Store API を含む Vertex AI API を有効化する。destroy 時に API を無効化しない。
resource "google_project_service" "vertex_ai" {
  project            = var.project_id
  service            = "aiplatform.googleapis.com"
  disable_on_destroy = false
}

# Session Store 専用の親 Agent Engine。spec を指定しないため、エージェントコードは配備しない。
resource "google_vertex_ai_reasoning_engine" "session_store" {
  project      = var.project_id
  region       = var.region
  display_name = var.agent_engine_display_name
  description  = "Claude Agent SDK と Session Store のプロセス間永続化検証専用リソース"

  depends_on = [google_project_service.vertex_ai]
}
