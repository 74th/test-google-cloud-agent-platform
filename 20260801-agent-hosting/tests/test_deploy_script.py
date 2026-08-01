import os
import subprocess


def test_missing_deploy_configuration_does_not_echo_api_key() -> None:
    env = {"PATH": os.environ["PATH"], "ANTHROPIC_API_KEY": "must-not-appear"}
    result = subprocess.run(["./scripts/deploy.sh"], env=env, text=True, capture_output=True, check=False)
    assert result.returncode == 2
    assert "Terraform CLI" in result.stderr
    assert "must-not-appear" not in result.stdout + result.stderr


def test_deploy_requires_terraform_managed_service_account() -> None:
    env = {
        "PATH": os.environ["PATH"],
        "LOCATION": "us-central1",
        "VERTEX_PROJECT_ID": "nnyn-dev",
        "VERTEX_REGION": "global",
    }
    result = subprocess.run(["./scripts/deploy.sh"], env=env, text=True, capture_output=True, check=False)
    assert result.returncode == 2
    assert "Terraform CLI" in result.stderr


def test_deploy_builds_and_pushes_with_local_docker() -> None:
    script = open("scripts/deploy.sh").read()
    assert 'gcloud auth configure-docker "${LOCATION}-docker.pkg.dev" --quiet' in script
    assert 'docker build --tag "$IMAGE_URI" .' in script
    assert 'docker push "$IMAGE_URI"' in script
    assert "gcloud builds submit" not in script
