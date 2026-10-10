output "project_id" {
  value       = var.project_id
  description = "Explicit project containing the isolated research environment."
}

output "location" {
  value       = var.region
  description = "GKE cluster and registry region."
}

output "cluster_name" {
  value = google_container_cluster.sandbox.name
}

output "cluster_self_link" {
  value = google_container_cluster.sandbox.self_link
}

output "network_name" {
  value = google_compute_network.sandbox.name
}

output "subnetwork_name" {
  value = google_compute_subnetwork.sandbox.name
}

output "pod_secondary_range_name" {
  value = local.pods_range_name
}

output "service_secondary_range_name" {
  value = local.services_range_name
}

output "registry_name" {
  value = google_artifact_registry_repository.images.repository_id
}

output "registry_location" {
  value = google_artifact_registry_repository.images.location
}

output "registry_url" {
  value = "${google_artifact_registry_repository.images.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "node_pool_names" {
  value = {
    system = google_container_node_pool.system.name
    gvisor = google_container_node_pool.gvisor.name
  }
}

output "physical_name_mapping" {
  value = {
    cluster                 = local.cluster_name
    vpc                     = local.vpc_name
    subnet                  = local.subnet_name
    router                  = local.router_name
    nat                     = local.nat_name
    registry                = local.registry_name
    system_node_pool        = local.system_pool_name
    gvisor_node_pool        = local.gvisor_pool_name
    node_service_account_id = local.node_service_account
    pod_secondary_range     = local.pods_range_name
    service_secondary_range = local.services_range_name
  }
}

output "get_credentials_command" {
  value       = "gcloud container clusters get-credentials ${google_container_cluster.sandbox.name} --region ${var.region} --project ${var.project_id}"
  description = "Explicit command to configure kubectl for this cluster."
}
