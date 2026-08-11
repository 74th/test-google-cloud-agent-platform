output "project_id" {
  description = "デプロイスクリプトで使用する Google Cloud プロジェクト ID。"
  value       = var.project_id
}

output "cluster_name" {
  description = "GKE クラスタ名。"
  value       = google_container_cluster.isolated.name
}

output "cluster_location" {
  description = "GKE クラスタのロケーション。"
  value       = google_container_cluster.isolated.location
}

output "zone" {
  description = "GKE クラスタのゾーン。"
  value       = var.zone
}

output "network_name" {
  description = "data source で選択した VPC ネットワーク名。"
  value       = data.google_compute_network.default.name
}

output "subnetwork_name" {
  description = "data source で選択したサブネット名。"
  value       = data.google_compute_subnetwork.default.name
}

output "workload_iam_principal" {
  description = "Kubernetes ServiceAccount に対応する直接指定 IAM principal。"
  value       = local.workload_iam_principal
}

output "image_repository" {
  description = "コンテナイメージ用 Artifact Registry リポジトリ URL。"
  value       = "${var.artifact_registry_location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agent.repository_id}"
}

output "image_uri" {
  description = "デプロイスクリプトで使用する既定のイメージ URI。"
  value       = "${var.artifact_registry_location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agent.repository_id}/test:latest"
}

output "artifact_repository_id" {
  description = "Terraform が所有する Artifact Registry リポジトリ ID。"
  value       = google_artifact_registry_repository.agent.repository_id
}

output "artifact_registry_location" {
  description = "Terraform が所有する Artifact Registry のロケーション。"
  value       = google_artifact_registry_repository.agent.location
}
