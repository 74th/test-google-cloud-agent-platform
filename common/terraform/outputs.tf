output "agent_gateway_id" {
  description = "Fully qualified shared Agent Gateway resource ID for explicit consumer input."
  value       = google_network_services_agent_gateway.shared.id
}

output "network_id" {
  description = "Fully qualified ID of the dedicated shared VPC."
  value       = google_compute_network.agent_gateway.id
}

output "subnetwork_id" {
  description = "Fully qualified ID of the dedicated PSC interface subnet."
  value       = google_compute_subnetwork.agent_gateway.id
}

output "network_attachment_id" {
  description = "Fully qualified URI of the PSC interface Network Attachment used by Agent Gateway."
  value       = google_compute_network_attachment.agent_gateway.self_link
}
