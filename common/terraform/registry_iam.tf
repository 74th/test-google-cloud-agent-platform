# The validation Runtime is an explicit common-Gateway consumer. The binding
# is imported from the former validation checkout during the ownership move.
resource "google_iap_agent_registry_endpoint_iam_member" "github_runtime_124" {
  provider = google-nightly

  project     = var.project_id
  location    = var.region
  endpoint_id = data.google_agent_registry_endpoint.github.endpoint_id
  role        = "roles/iap.egressor"
  member      = "principal://agents.global.proj-776113568960.system.id.goog/resources/aiplatform/projects/776113568960/locations/us-central1/reasoningEngines/124453171392151552"
}

# The first post-migration probe reached the common Vertex global endpoint and
# was denied by IAP Authz. Keep this binding resource-scoped and Runtime-scoped.
resource "google_iap_agent_registry_endpoint_iam_member" "aiplatform_global_runtime_124" {
  provider = google-nightly

  project     = var.project_id
  location    = var.region
  endpoint_id = data.google_agent_registry_endpoint.aiplatform_global.endpoint_id
  role        = "roles/iap.egressor"
  member      = "principal://agents.global.proj-776113568960.system.id.goog/resources/aiplatform/projects/776113568960/locations/us-central1/reasoningEngines/124453171392151552"
}
