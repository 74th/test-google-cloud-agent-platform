# The common Registry endpoint resources are read-only dependencies. This
# consumer owns the Runtime-specific egress grants for its own effective
# identity and must not create, import, or mutate the common endpoints.
resource "google_iap_agent_registry_endpoint_iam_member" "runtime" {
  for_each = data.google_agent_registry_endpoint.common
  provider = google-nightly

  project     = var.project_id
  location    = var.region
  endpoint_id = each.value.endpoint_id
  role        = "roles/iap.egressor"
  member      = "principal://${google_vertex_ai_reasoning_engine.runtime.spec[0].effective_identity}"
}
