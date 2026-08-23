data "google_agent_registry_endpoint" "github" {
  provider = google-nightly

  project  = var.project_id
  location = var.location
  filter   = "displayName=\"${google_agent_registry_service.services["github"].display_name}\""

  depends_on = [google_agent_registry_service.services["github"]]
}

resource "google_iap_agent_registry_endpoint_iam_member" "github" {
  provider = google-nightly

  project     = var.project_id
  location    = var.location
  endpoint_id = data.google_agent_registry_endpoint.github.endpoint_id
  role        = "roles/iap.egressor"
  member      = "principal://${google_vertex_ai_reasoning_engine.runtime.spec[0].effective_identity}"
}
