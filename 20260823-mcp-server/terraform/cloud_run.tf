resource "google_cloud_run_v2_service" "mcp" {
  name                = "${var.name_prefix}-run"
  location            = var.region
  project             = var.project_id
  ingress             = "INGRESS_TRAFFIC_ALL"
  labels              = local.common_labels
  deletion_protection = false

  template {
    service_account = google_service_account.cloud_run_runtime.email
    labels          = local.common_labels

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = local.container_image

      ports {
        container_port = 8080
      }
    }
  }

  lifecycle {
    precondition {
      condition     = can(regex("@sha256:[0-9a-f]{64}$", local.container_image))
      error_message = "Cloud Run must use an immutable image digest."
    }
  }

  depends_on = [google_project_service.required, google_artifact_registry_repository.mcp]
}

resource "google_cloud_run_v2_service_iam_member" "test_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.mcp.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.test_invoker.email}"
}

resource "google_cloud_run_v2_service_iam_member" "mcp_caller" {
  count    = var.use_mcp_caller_service_account ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.mcp.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.mcp_caller[0].email}"
}
