output "agent_engine_name" {
  description = ".env の GOOGLE_CLOUD_AGENT_ENGINE に設定する完全リソース名"
  value       = "projects/${var.project_id}/locations/${var.region}/reasoningEngines/${google_vertex_ai_reasoning_engine.session_store.name}"
}
