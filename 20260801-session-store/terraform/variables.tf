variable "project_id" {
  description = "Agent Engine と Session Store を作成する Google Cloud プロジェクト ID"
  type        = string
  default     = "nnyn-dev"
}

variable "region" {
  description = "Agent Engine を作成するリージョン。アプリケーションの GOOGLE_CLOUD_LOCATION と一致させる。"
  type        = string
  default     = "us-central1"
}

variable "agent_engine_display_name" {
  description = "Session Store 検証専用 Agent Engine の表示名"
  type        = string
  default     = "claude-session-store-verification"
}
