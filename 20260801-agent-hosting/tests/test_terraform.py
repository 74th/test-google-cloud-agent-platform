from pathlib import Path


TERRAFORM = Path("terraform")


def test_runtime_identity_is_scoped_to_vertex_ai() -> None:
    main = (TERRAFORM / "main.tf").read_text()
    assert 'account_id   = "claude-agent-runtime"' in main
    assert "2026-08-01 20260801-agent-hosting" in main
    assert 'role    = "roles/aiplatform.user"' in main
    assert "secretmanager" not in main
    assert "roles/editor" not in main.lower()
    assert "roles/owner" not in main.lower()


def test_terraform_uses_us_central1_and_does_not_contain_api_key() -> None:
    variables = (TERRAFORM / "variables.tf").read_text()
    example = (TERRAFORM / "terraform.tfvars.example").read_text()
    assert 'default     = "us-central1"' in variables
    assert "claude_secret_id" not in variables
    assert "claude_secret_id" not in example
    assert "ANTHROPIC_API_KEY" not in (TERRAFORM / "main.tf").read_text()


def test_terraform_manages_the_test_container_repository() -> None:
    main = (TERRAFORM / "main.tf").read_text()
    outputs = (TERRAFORM / "outputs.tf").read_text()
    assert 'service            = "artifactregistry.googleapis.com"' in main
    assert "cloudbuild.googleapis.com" not in main
    assert 'repository_id = "agent-hosting-20260801"' in main
    assert "2026-08-01 20260801-agent-hosting" in main
    assert 'role       = "roles/artifactregistry.reader"' in main
    assert "gcp-sa-aiplatform-re.iam.gserviceaccount.com" in main
    assert 'output "artifact_registry_repository_id"' in outputs
