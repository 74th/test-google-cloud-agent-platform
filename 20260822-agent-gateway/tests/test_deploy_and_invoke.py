import argparse
import json

import pytest

from scripts import deploy_agent, gateway, invoke_agent


def test_deploy_config_has_full_gateway_and_vertex_environment() -> None:
    args = argparse.Namespace(
        display_name="agent",
        image_uri="us-central1-docker.pkg.dev/nnyn-dev/repo/image:latest",
        vertex_project="nnyn-dev",
        vertex_region="global",
        service_account="runtime@nnyn-dev.iam.gserviceaccount.com",
        agent_gateway="projects/nnyn-dev/locations/us-central1/agentGateways/agw-20260822-egress",
    )
    config = deploy_agent.build_config(args)
    assert config["env_vars"]["ANTHROPIC_MODEL"] == deploy_agent.VERTEX_HAIKU_MODEL
    assert config["env_vars"]["ANTHROPIC_VERTEX_PROJECT_ID"] == "nnyn-dev"
    assert config["env_vars"]["CLOUD_ML_REGION"] == "global"
    assert "AGENT_GATEWAY_RESOURCE" not in config["env_vars"]
    assert config["service_account"].endswith("gserviceaccount.com")


def test_gateway_patch_uses_agent_to_anywhere_config() -> None:
    patch = deploy_agent.gateway_patch("projects/x", "projects/p/locations/r/agentGateways/g")
    assert patch["spec"]["deploymentSpec"]["agentGatewayConfig"]["agentToAnywhereConfig"]["agentGateway"].endswith("/g")


def test_invoke_requires_full_resource_and_uses_query() -> None:
    with pytest.raises(ValueError):
        invoke_agent.endpoint("agent", "us-central1")
    assert invoke_agent.endpoint("projects/p/locations/r/reasoningEngines/a", "us-central1").endswith(":query")


def test_invoke_rejects_invalid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(invoke_agent, "token", lambda: "token")

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return json.dumps({"unexpected": "value"}).encode()

    monkeypatch.setattr(invoke_agent.urllib.request, "urlopen", lambda *a, **k: Response())
    with pytest.raises(RuntimeError, match="有効なテキスト応答"):
        invoke_agent.invoke("projects/p/locations/r/reasoningEngines/a", "us-central1", "hi")


def test_gateway_commands_and_paging() -> None:
    command = gateway.github_service_command("nnyn-dev", "us-central1", "agw-20260822-github")
    assert "https://github.com" in " ".join(command)
    assert "www8.cao.go.jp" not in " ".join(command)

    pages = iter(
        [
            {"entries": [{"host": "github.com"}], "nextPageToken": "next"},
            {"entries": [{"host": "target"}]},
        ]
    )
    assert gateway.collect_log_pages(lambda _: next(pages)) == [{"host": "github.com"}, {"host": "target"}]

    managed = gateway.essential_google_service_command("nnyn-dev", "us-central1", "aiplatform")
    assert "https://aiplatform.googleapis.com" in " ".join(managed)
    assert "www8.cao.go.jp" not in " ".join(managed)


def test_allow_policy_rejects_unqualified_principal():
    with pytest.raises(ValueError):
        gateway.allow_policy("serviceAccount:runtime@example.com")
