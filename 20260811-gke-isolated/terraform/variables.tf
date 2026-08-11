variable "project_id" {
  description = "クラスタと KSA IAM principal を所有する Google Cloud プロジェクト。"
  type        = string
}

variable "region" {
  description = "既存の default subnet が存在するリージョン。"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "ゾーンクラスタを配置する単一ゾーン。"
  type        = string
  default     = "us-central1-a"
}

variable "cluster_name" {
  description = "GKE クラスタ名。"
  type        = string
  default     = "test-isolated"
}

variable "network_name" {
  description = "使用する既存の VPC ネットワーク名。"
  type        = string
  default     = "default"
}

variable "subnetwork_name" {
  description = "使用する既存のサブネット名。"
  type        = string
  default     = "default"
}

variable "machine_type" {
  description = "ノードのマシンタイプ。"
  type        = string
  default     = "e2-standard-2"
}

variable "release_channel" {
  description = "GKE のリリースチャネル。"
  type        = string
  default     = "REGULAR"
}

variable "artifact_registry_location" {
  description = "Artifact Registry のロケーション。"
  type        = string
  default     = "us-central1"
}

variable "artifact_repository_id" {
  description = "Artifact Registry リポジトリ ID。"
  type        = string
  default     = "test-gke-isolated"
}

variable "kubernetes_namespace" {
  description = "直接指定する Workload Identity principal に含める Kubernetes namespace。"
  type        = string
  default     = "default"
}

variable "kubernetes_service_account" {
  description = "直接指定する IAM principal に含める Kubernetes ServiceAccount 名。"
  type        = string
  default     = "test"
}
