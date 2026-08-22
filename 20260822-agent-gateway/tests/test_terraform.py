from pathlib import Path


TERRAFORM = Path("terraform")


def test_gateway_is_default_deny_and_only_github_is_web_allow() -> None:
    policy = (TERRAFORM / "egress-policy.yaml").read_text()
    assert "mode: AGENT_TO_ANYWHERE" in policy
    assert "default_action: DENY" in policy
    assert "host: github.com" in policy
    assert "www8.cao.go.jp" not in policy
    assert "deny:" not in policy.lower()


def test_gateway_uses_official_resource_and_fixed_nightly_provider() -> None:
    versions = (TERRAFORM / "versions.tf").read_text()
    main = (TERRAFORM / "main.tf").read_text()
    assert 'source  = "hashicorp/google-nightly"' in versions
    assert 'version = "2026.4.8-7.27.0"' in versions
    assert "google_network_services_agent_gateway" in main
    assert 'governed_access_path = "AGENT_TO_ANYWHERE"' in main
    assert "20260801-agent-hosting" not in main
    assert "claude-agent-runtime" not in main


def test_iam_is_narrow_and_no_secret_manager_or_api_key() -> None:
    main = (TERRAFORM / "main.tf").read_text()
    assert 'role    = "roles/aiplatform.user"' in main
    assert 'role       = "roles/artifactregistry.reader"' in main
    assert "secretmanager" not in main.lower()
    assert "roles/editor" not in main.lower()
    assert "roles/owner" not in main.lower()
    assert "ANTHROPIC_API_KEY" not in main


def test_required_project_and_vertex_defaults() -> None:
    variables = (TERRAFORM / "variables.tf").read_text()
    assert 'default     = "nnyn-dev"' in variables
    assert 'default     = "us-central1"' in variables
    assert 'default     = "global"' in variables
