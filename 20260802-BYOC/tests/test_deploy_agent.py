import argparse
import json

import pytest

from scripts.deploy_agent import (
    CLASS_METHODS,
    build_config,
    build_rest_create_payload,
    classify_gateway_error,
    deployment_result,
    failure_evidence,
    rest_create_runtime,
    sdk_create_config,
    validate_agent_gateway,
    validate_image_digest,
    verify_runtime_configuration,
)

IMAGE = "us-central1-docker.pkg.dev/nnyn-dev/byoc-query-verification/byoc-query-verification@sha256:" + "a" * 64
GATEWAY = "projects/nnyn-dev/locations/us-central1/agentGateways/common-egress"


def make_args(**overrides):
    values = {
        "project": "nnyn-dev",
        "location": "us-central1",
        "agent_gateway": GATEWAY,
        "image_uri": IMAGE,
        "service_account": "byoc-query-runtime@nnyn-dev.iam.gserviceaccount.com",
        "identity_type": "SERVICE_ACCOUNT",
        "display_name": "test-runtime",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_validate_agent_gateway_accepts_fully_qualified_reference():
    assert validate_agent_gateway(GATEWAY, project="nnyn-dev", location="us-central1")["name"] == "common-egress"


@pytest.mark.parametrize("gateway", ["common-egress", "projects/p/locations/l/agentGateways", "projects/p/locations/l/other/g"])
def test_validate_agent_gateway_rejects_invalid_format(gateway):
    with pytest.raises(ValueError, match="must be"):
        validate_agent_gateway(gateway, project="p", location="l")


def test_validate_agent_gateway_rejects_project_and_location_mismatch():
    with pytest.raises(ValueError, match="project"):
        validate_agent_gateway(GATEWAY, project="other", location="us-central1")
    with pytest.raises(ValueError, match="location"):
        validate_agent_gateway(GATEWAY, project="nnyn-dev", location="europe-west1")


def test_build_config_keeps_gateway_and_existing_runtime_contract():
    config = build_config(make_args())
    assert config["agent_framework"] == "custom"
    assert config["container_spec"]["image_uri"] == IMAGE
    assert config["class_methods"] == CLASS_METHODS
    assert config["service_account"]
    assert config["identity_type"] == "SERVICE_ACCOUNT"
    assert config["agent_gateway_config"]["agent_to_anywhere_config"]["agent_gateway"] == GATEWAY


def test_sdk_serialization_contract_preserves_gateway():
    import agentplatform

    client = agentplatform.Client(project="nnyn-dev", location="us-central1")
    serialized = sdk_create_config(client, build_config(make_args()))
    assert serialized["spec"]["deployment_spec"]["agent_gateway_config"]["agent_to_anywhere_config"]["agent_gateway"] == GATEWAY


def test_rest_payload_has_atomic_gateway_and_runtime_fields():
    spec = build_rest_create_payload(build_config(make_args()))["spec"]
    assert spec["deploymentSpec"]["agentGatewayConfig"]["agentToAnywhereConfig"]["agentGateway"] == GATEWAY
    assert spec["containerSpec"]["imageUri"] == IMAGE
    assert spec["classMethods"] == CLASS_METHODS
    assert spec["serviceAccount"]
    assert spec["identityType"] == "SERVICE_ACCOUNT"


def test_agent_identity_gateway_payload_does_not_send_service_account():
    config = build_config(make_args(identity_type="AGENT_IDENTITY"))
    assert config["service_account"] is None
    spec = build_rest_create_payload(config)["spec"]
    assert spec["identityType"] == "AGENT_IDENTITY"
    assert "serviceAccount" not in spec


def runtime(gateway=GATEWAY, image=IMAGE, identity="SERVICE_ACCOUNT"):
    return {
        "name": "projects/776113568960/locations/us-central1/reasoningEngines/123",
        "spec": {
            "identityType": identity,
            "effectiveIdentity": "byoc-query-runtime@nnyn-dev.iam.gserviceaccount.com",
            "containerSpec": {"imageUri": image},
            "deploymentSpec": {"agentGatewayConfig": {"agentToAnywhereConfig": {"agentGateway": gateway}}},
        },
        "trafficConfig": {"latest": 100},
    }


def test_runtime_verifier_checks_live_gateway_identity_digest_and_traffic():
    metadata = verify_runtime_configuration(runtime(), expected_gateway=GATEWAY, expected_image_uri=IMAGE, expected_identity_type="SERVICE_ACCOUNT")
    assert metadata["image_digest"] == "sha256:" + "a" * 64
    assert metadata["traffic"] == {"latest": 100}


def test_runtime_verifier_accepts_byoc_get_without_revision_or_traffic():
    body = runtime()
    body.pop("trafficConfig")
    metadata = verify_runtime_configuration(body, expected_gateway=GATEWAY, expected_image_uri=IMAGE, expected_identity_type="SERVICE_ACCOUNT")
    assert metadata["revision"] is None
    assert metadata["traffic"] is None


@pytest.mark.parametrize("changed", [{"gateway": "projects/nnyn-dev/locations/us-central1/agentGateways/wrong"}, {"identity": "AGENT_IDENTITY"}, {"image": IMAGE.replace("a" * 64, "b" * 64)}])
def test_runtime_verifier_fails_closed_on_mismatch(changed):
    with pytest.raises(ValueError):
        verify_runtime_configuration(runtime(**changed), expected_gateway=GATEWAY, expected_image_uri=IMAGE, expected_identity_type="SERVICE_ACCOUNT")


def test_result_allowlist_excludes_operation_schemas_and_secrets():
    metadata = {"resource_name": "projects/p/locations/l/reasoningEngines/1", "image_digest": "sha256:" + "a" * 64, "gateway_id": GATEWAY, "identity_type": "SERVICE_ACCOUNT", "effective_identity": "byoc-query-runtime@nnyn-dev.iam.gserviceaccount.com", "revision": None, "traffic": {"latest": 100}}
    result = deployment_result(metadata, deployed_at="2026-08-28T00:00:00+00:00")
    serialized = json.dumps(result)
    assert set(result) == {"resource_name", "image_digest", "gateway_id", "identity", "deployed_at"}
    assert "operation_schemas" not in serialized
    assert "token" not in serialized.lower()


class Response:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class Session:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return Response(200, {"name": "projects/p/locations/l/operations/1"})

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return Response(200, {"done": True, "response": {"name": "projects/p/locations/l/reasoningEngines/1"}})


def test_rest_fallback_uses_atomic_payload_and_polls_operation():
    session = Session()
    response = rest_create_runtime(session, project="p", location="l", payload={"spec": {"agentGatewayConfig": {"agentGateway": GATEWAY}}}, poll_interval=0, max_polls=1)
    assert response["name"].endswith("reasoningEngines/1")
    assert [call[0] for call in session.calls] == ["POST", "GET"]
    assert session.calls[0][1].endswith("/reasoningEngines")
    assert session.calls[1][1].endswith("/operations/1")


def test_image_digest_is_immutable():
    assert validate_image_digest(IMAGE) == "sha256:" + "a" * 64
    with pytest.raises(ValueError):
        validate_image_digest(IMAGE.split("@", 1)[0] + ":latest")


def test_error_classification_is_safe():
    assert classify_gateway_error(RuntimeError("already active or being created")) == "gateway_conflict"
    assert classify_gateway_error(RuntimeError("permission denied; Authorization: Bearer secret")) == "permission_denied"


def test_failure_evidence_is_safe_and_declares_no_workaround():
    result = failure_evidence(gateway_id=GATEWAY, target_runtime="projects/p/locations/l/reasoningEngines/1", exc=RuntimeError("conflict"))
    assert result["error"]["classification"] == "gateway_conflict"
    assert result["target_runtime"].endswith("/1")
    assert result["gatewayless_retry"] is False
    assert result["existing_runtime_modified"] is False
    assert result["common_resource_modified"] is False
    assert "Authorization" not in json.dumps(result)
