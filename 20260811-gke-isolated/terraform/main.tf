terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0, < 8.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 6.0, < 8.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.25, < 3.0"
    }
  }
}

# この構成で利用する通常版 Google Cloud provider。
provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# GKE の先行機能を利用するための Google Beta provider。
provider "google-beta" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# テストクラスタ用に新しいネットワークを作成せず、既存の VPC を参照する。
data "google_compute_network" "default" {
  name = var.network_name
}

# ゾーンクラスタで使用する既存のリージョナルな default subnet を参照する。
data "google_compute_subnetwork" "default" {
  name   = var.subnetwork_name
  region = var.region
}

# KSA principal URI に必要なプロジェクト番号を取得する。
data "google_project" "current" {
  project_id = var.project_id
}

# GKE、Artifact Registry、IAM、Vertex AI、BigQuery、Workload Identity に必要な API。
locals {
  required_services = toset([
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "container.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "serviceusage.googleapis.com",
    "sts.googleapis.com",
  ])

  # default namespace の test KSA が使用する直接指定の Workload Identity principal。
  workload_iam_principal = "principal://iam.googleapis.com/projects/${data.google_project.current.number}/locations/global/workloadIdentityPools/${var.project_id}.svc.id.goog/subject/ns/${var.kubernetes_namespace}/sa/${var.kubernetes_service_account}"
}

# API を有効化する。Terraform destroy 時にも API は無効化しない。
resource "google_project_service" "required" {
  for_each = local.required_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Workload Identity Federation for GKE を有効にした単一ゾーン Dataplane V2 クラスタ。
resource "google_container_cluster" "isolated" {
  provider = google-beta

  name     = var.cluster_name
  location = var.zone

  network    = data.google_compute_network.default.id
  subnetwork = data.google_compute_subnetwork.default.id

  remove_default_node_pool = true
  initial_node_count       = 1

  networking_mode   = "VPC_NATIVE"
  datapath_provider = "ADVANCED_DATAPATH"

  ip_allocation_policy {}

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # FQDNNetworkPolicy は Dataplane V2 の機能であり、k8s/ から別途適用する。
  enable_fqdn_network_policy = true

  release_channel {
    channel = var.release_channel
  }

  deletion_protection = false

  depends_on = [google_project_service.required]
}

# GKE Metadata Server を使用する e2-standard-2・1台固定のノードプール。
resource "google_container_node_pool" "isolated" {
  provider = google-beta

  name       = "test-isolated-pool"
  cluster    = google_container_cluster.isolated.name
  location   = var.zone
  node_count = 1

  autoscaling {
    min_node_count = 1
    max_node_count = 1
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type = var.machine_type
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }
}

# ワークロードイメージの build とデプロイスクリプトで使用する Docker リポジトリ。
resource "google_artifact_registry_repository" "agent" {
  location      = var.artifact_registry_location
  repository_id = var.artifact_repository_id
  description   = "Claude Agent SDK 検証用イメージ"
  format        = "DOCKER"

  depends_on = [google_project_service.required]
}

# Kubernetes ServiceAccount principal に必要最小限のプロジェクト IAM role を直接付与する。
resource "google_project_iam_member" "workload_roles" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/bigquery.jobUser",
  ])

  project = var.project_id
  role    = each.value
  member  = local.workload_iam_principal
}
