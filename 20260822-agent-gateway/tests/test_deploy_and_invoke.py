import argparse
import json

import pytest

from scripts import deploy_agent, gateway, invoke_agent


GATEWAY = "projects/nnyn-dev/locations/us-central1/agentGateways/common-egress"
IMAGE = "us-central1-docker.pkg.dev/nnyn-dev/repo/image@sha256:" + "a" * 64


def args(**overrides):
    values = {
        "display_name": "agent",
        "image_uri": IMAGE,
        "project": "nnyn-dev",
        "location": "us-central1",
        "vertex_project": "nnyn-dev",
        "vertex_region": "global",
        "agent_gateway": GATEWAY,
        "identity_type": "AGENT_IDENTITY",
        "service_account": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_deploy_config_has_full_gateway_and_vertex_environment() -> None:
    config = deploy_agent.build_config(args())
    assert config["agent_gateway_config"]["agent_to_anywhere_config"]["agent_gateway"] == GATEWAY
    assert config["identity_type"] == "AGENT_IDENTITY"
    payload = deploy_agent.build_rest_create_payload(config)
    assert payload["spec"]["deploymentSpec"]["agentGatewayConfig"]["agentToAnywhereConfig"]["agentGateway"] == GATEWAY
    assert payload["spec"]["containerSpec"]["imageUri"] == IMAGE
    assert deploy_agent.redacted_create_preview(config) == payload


@pytest.mark.parametrize(
    "gateway",
    ["", "common-egress", "projects/other/locations/us-central1/agentGateways/g", GATEWAY.replace("us-central1", "europe-west1")],
)
def test_invalid_gateway_fails_closed(gateway):
    with pytest.raises(deploy_agent.GatewayValidationError):
        deploy_agent.validate_agent_gateway(gateway, project="nnyn-dev", location="us-central1")


def test_invoke_requires_full_resource_and_uses_query() -> None:
    with pytest.raises(ValueError):
        invoke_agent.endpoint("agent", "us-central1")
    assert invoke_agent.endpoint("projects/p/locations/us-central1/reasoningEngines/a", "us-central1").endswith(":query")


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
        invoke_agent.invoke("projects/p/locations/us-central1/reasoningEngines/a", "us-central1", "hi")


def test_invoke_uses_active_gcloud_credential_when_adc_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(invoke_agent, "adc_token", lambda: (_ for _ in ()).throw(RuntimeError("no ADC")))
    monkeypatch.setattr(invoke_agent, "gcloud_token", lambda: "ephemeral-gcloud-token")
    assert invoke_agent.token() == "ephemeral-gcloud-token"


def test_gateway_commands_and_paging() -> None:
    command = gateway.github_service_command("nnyn-dev", "us-central1", "agent-gateway-20260828-github")
    assert "https://github.com" in " ".join(command)
    assert "www8.cao.go.jp" not in " ".join(command)
    pages = iter([{"entries": [{"host": "github.com"}], "nextPageToken": "next"}, {"entries": [{"host": "target"}]}])
    assert gateway.collect_log_pages(lambda _: next(pages)) == [{"host": "github.com"}, {"host": "target"}]


def test_allow_policy_rejects_unqualified_principal():
    with pytest.raises(ValueError):
        gateway.allow_policy("serviceAccount:runtime@example.com")
