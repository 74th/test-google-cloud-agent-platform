"""Create a BYOC Runtime with an explicitly validated Agent Gateway."""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CLASS_METHODS = [
    {"name": "query", "api_mode": "", "parameters": {"type": "object", "properties": {"verification_id": {"type": "string"}}, "required": ["verification_id"]}},
    {"name": "async_query", "api_mode": "async", "parameters": {"type": "object", "properties": {"verification_id": {"type": "string"}}, "required": ["verification_id"]}},
    {"name": "stream_query", "api_mode": "stream", "parameters": {"type": "object", "properties": {"verification_id": {"type": "string"}}, "required": ["verification_id"]}},
    {"name": "async_stream_query", "api_mode": "async_stream", "parameters": {"type": "object", "properties": {"verification_id": {"type": "string"}}, "required": ["verification_id"]}},
]

GATEWAY_PATTERN = re.compile(
    r"^projects/(?P<project>[^/]+)/locations/(?P<location>[^/]+)/agentGateways/(?P<name>[^/]+)$"
)
IMAGE_DIGEST_PATTERN = re.compile(r"^.+@sha256:[0-9a-f]{64}$")


class GatewayValidationError(ValueError):
    """A fail-closed validation error safe to report to evidence."""

    def __init__(self, message: str, *, classification: str = "invalid_reference") -> None:
        super().__init__(message)
        self.classification = classification


class RuntimeConfigurationError(ValueError):
    """The created Runtime does not match the requested immutable contract."""


def validate_agent_gateway(agent_gateway: str, *, project: str, location: str) -> dict[str, str]:
    """Validate and parse a fully qualified Agent Gateway resource name."""
    match = GATEWAY_PATTERN.fullmatch(agent_gateway or "")
    if not match:
        raise GatewayValidationError(
            "--agent-gateway must be projects/<project>/locations/<location>/agentGateways/<name>"
        )
    values = match.groupdict()
    if values["project"] != project:
        raise GatewayValidationError("Agent Gateway project does not match --project")
    if values["location"] != location:
        raise GatewayValidationError("Agent Gateway location does not match --location")
    return {key: value for key, value in values.items() if value is not None}


def validate_image_digest(image_uri: str) -> str:
    """Require an immutable Artifact Registry image reference."""
    if not IMAGE_DIGEST_PATTERN.fullmatch(image_uri or ""):
        raise ValueError("--image-uri must contain an immutable @sha256:<64-hex> digest")
    return image_uri.rsplit("@", 1)[1]


def build_config(args: argparse.Namespace) -> dict[str, object]:
    """Build the SDK config, including the Gateway in the create request."""
    validate_agent_gateway(args.agent_gateway, project=args.project, location=args.location)
    identity_type = getattr(args, "identity_type", "SERVICE_ACCOUNT")
    service_account = args.service_account if identity_type == "SERVICE_ACCOUNT" else None
    return {
        "display_name": args.display_name,
        "agent_framework": "custom",
        "container_spec": {"image_uri": args.image_uri},
        "class_methods": CLASS_METHODS,
        "service_account": service_account,
        "identity_type": identity_type,
        "agent_gateway_config": {
            "agent_to_anywhere_config": {"agent_gateway": args.agent_gateway}
        },
    }


def build_rest_create_payload(config: dict[str, object]) -> dict[str, object]:
    """Convert the SDK-shaped config to the v1 Reasoning Engine wire shape."""
    container = config["container_spec"]
    gateway = config["agent_gateway_config"]
    assert isinstance(container, dict)
    assert isinstance(gateway, dict)
    anywhere = gateway["agent_to_anywhere_config"]
    assert isinstance(anywhere, dict)
    spec = {
        "displayName": config["display_name"],
        "spec": {
            "classMethods": config["class_methods"],
            "containerSpec": {"imageUri": container["image_uri"]},
            "deploymentSpec": {
                "agentGatewayConfig": {
                    "agentToAnywhereConfig": {"agentGateway": anywhere["agent_gateway"]}
                }
            },
            "agentFramework": config["agent_framework"],
            "identityType": config["identity_type"],
        },
    }
    if config["service_account"] is not None:
        spec["spec"]["serviceAccount"] = config["service_account"]
    return spec


def sdk_create_config(client: Any, config: dict[str, object]) -> dict[str, object]:
    """Ask the installed SDK to serialize its create config before sending it."""
    api_config = client.agent_engines._create_config(
        mode="create",
        display_name=config["display_name"],
        agent_framework=config["agent_framework"],
        container_spec=config["container_spec"],
        class_methods=config["class_methods"],
        service_account=config["service_account"],
        identity_type=config["identity_type"],
        agent_gateway_config=config["agent_gateway_config"],
    )
    if not _contains_value(
        api_config,
        config["agent_gateway_config"]["agent_to_anywhere_config"]["agent_gateway"],
    ):
        raise GatewayValidationError(
            "Agent Platform SDK removed agent_gateway from the serialized create config",
            classification="sdk_serialization_unsupported",
        )
    return api_config


def _contains_value(value: Any, expected: object) -> bool:
    if value == expected:
        return True
    if isinstance(value, dict):
        return any(_contains_value(item, expected) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_value(item, expected) for item in value)
    return False


def _as_dict(resource: Any) -> dict[str, Any]:
    if isinstance(resource, dict):
        return resource
    if hasattr(resource, "model_dump"):
        return resource.model_dump(by_alias=True, exclude_none=False)
    if hasattr(resource, "__dict__"):
        return dict(resource.__dict__)
    raise RuntimeConfigurationError("Runtime GET returned an unsupported response shape")


def runtime_metadata(resource: Any) -> dict[str, Any]:
    """Extract only non-secret Runtime fields needed by the deployment contract."""
    body = _as_dict(resource)
    spec = body.get("spec") or {}
    deployment = spec.get("deploymentSpec") or {}
    gateway_config = deployment.get("agentGatewayConfig") or {}
    anywhere = gateway_config.get("agentToAnywhereConfig") or {}
    container = spec.get("containerSpec") or {}
    image_uri = container.get("imageUri")
    digest = image_uri.rsplit("@", 1)[1] if isinstance(image_uri, str) and "@" in image_uri else None
    revision = (
        body.get("revision")
        or spec.get("revision")
        or deployment.get("revision")
        or (body.get("deployedModels") or [{}])[0].get("deployedModelId")
    )
    traffic = body.get("traffic") or body.get("trafficConfig") or spec.get("trafficConfig")
    return {
        "resource_name": body.get("name"),
        "gateway_id": anywhere.get("agentGateway"),
        "identity_type": spec.get("identityType"),
        "effective_identity": spec.get("effectiveIdentity"),
        "image_uri": image_uri,
        "image_digest": digest,
        "revision": revision,
        "traffic": traffic,
    }


def verify_runtime_configuration(
    resource: Any,
    *,
    expected_gateway: str,
    expected_image_uri: str,
    expected_identity_type: str,
) -> dict[str, Any]:
    """Fail closed unless the live Runtime matches the atomic create request."""
    actual = runtime_metadata(resource)
    expected_digest = validate_image_digest(expected_image_uri)
    mismatches = {}
    if actual["gateway_id"] != expected_gateway:
        mismatches["gateway_id"] = "mismatch"
    if actual["identity_type"] != expected_identity_type:
        mismatches["identity_type"] = "mismatch"
    if actual["image_digest"] != expected_digest:
        mismatches["image_digest"] = "mismatch"
    if mismatches:
        raise RuntimeConfigurationError(
            "Runtime GET did not match the requested Gateway, identity, image, or revision/traffic"
        )
    return actual


def deployment_result(metadata: dict[str, Any], *, deployed_at: str) -> dict[str, Any]:
    """Return the allowlisted deployment evidence schema."""
    return {
        "resource_name": metadata["resource_name"],
        "image_digest": metadata["image_digest"],
        "gateway_id": metadata["gateway_id"],
        "identity": {
            "type": metadata["identity_type"],
            "effective": metadata["effective_identity"],
        },
        "deployed_at": deployed_at,
    }


def classify_gateway_error(exc: BaseException) -> str:
    """Classify errors without persisting API bodies, tokens, or headers."""
    status = getattr(exc, "status_code", getattr(exc, "code", None))
    text = str(exc).lower()
    if isinstance(exc, RuntimeConfigurationError):
        return "runtime_configuration_mismatch"
    if isinstance(exc, TimeoutError):
        return "operation_timeout"
    if status == 403 or "permission" in text or "forbidden" in text:
        return "permission_denied"
    if status == 409 or "conflict" in text or "already active" in text:
        return "gateway_conflict"
    if status == 404 or "not found" in text or "invalid" in text or "reference" in text:
        return "invalid_reference"
    return "unknown_gateway_error"


def safe_error(exc: BaseException) -> dict[str, str]:
    return {"error_type": type(exc).__name__, "classification": classify_gateway_error(exc)}


def failure_evidence(*, gateway_id: str, exc: BaseException, target_runtime: str | None = None) -> dict[str, Any]:
    """Build safe create-failure evidence without a response body or retry."""
    return {
        "operation": "runtime_create",
        "target_runtime": target_runtime,
        "gateway_id": gateway_id,
        "error": safe_error(exc),
        "gatewayless_retry": False,
        "existing_runtime_modified": False,
        "common_resource_modified": False,
    }


def rest_create_runtime(
    session: Any,
    *,
    project: str,
    location: str,
    payload: dict[str, object],
    poll_interval: float = 10.0,
    max_polls: int = 180,
) -> dict[str, Any]:
    """Create and poll a Runtime using the same v1 payload as the SDK path."""
    base = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}"
    response = session.post(f"{base}/reasoningEngines", json=payload, timeout=30)
    if int(response.status_code) >= 400:
        error = RuntimeError(f"Runtime create returned HTTP {response.status_code}")
        error.status_code = int(response.status_code)  # type: ignore[attr-defined]
        raise error
    operation = response.json()
    if operation.get("done"):
        if operation.get("error"):
            raise RuntimeError("Runtime create operation failed")
        return operation.get("response") or {}
    operation_name = operation.get("name")
    if not isinstance(operation_name, str) or not operation_name:
        raise RuntimeError("Runtime create response did not include an operation name")
    operation_url = f"https://{location}-aiplatform.googleapis.com/v1/{operation_name.lstrip('/')}"
    for _ in range(max_polls):
        if poll_interval:
            time.sleep(poll_interval)
        poll = session.get(operation_url, timeout=30)
        if int(poll.status_code) >= 400:
            error = RuntimeError(f"Runtime operation polling returned HTTP {poll.status_code}")
            error.status_code = int(poll.status_code)  # type: ignore[attr-defined]
            raise error
        operation = poll.json()
        if operation.get("done"):
            if operation.get("error"):
                raise RuntimeError("Runtime create operation failed")
            return operation.get("response") or {}
    raise TimeoutError("Runtime create operation did not complete before the polling limit")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--agent-gateway", required=True)
    parser.add_argument("--image-uri", required=True)
    parser.add_argument("--service-account", required=True)
    parser.add_argument("--identity-type", choices=("SERVICE_ACCOUNT", "AGENT_IDENTITY"), default="AGENT_IDENTITY")
    parser.add_argument("--display-name", default="byoc-query-verification")
    parser.add_argument("--result", type=Path, default=Path("results/deployment.json"))
    args = parser.parse_args()
    target_runtime = None
    try:
        validate_agent_gateway(args.agent_gateway, project=args.project, location=args.location)
        validate_image_digest(args.image_uri)
        config = build_config(args)
        import agentplatform

        client = agentplatform.Client(project=args.project, location=args.location)
        try:
            sdk_create_config(client, config)
            remote = client.agent_engines.create(config=config)
            resource_name = remote.api_resource.name
            target_runtime = resource_name
            live = client.agent_engines.get(name=resource_name)
        except GatewayValidationError as exc:
            if exc.classification != "sdk_serialization_unsupported":
                raise
            import google.auth
            from google.auth.transport.requests import AuthorizedSession

            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            live = rest_create_runtime(
                AuthorizedSession(credentials),
                project=args.project,
                location=args.location,
                payload=build_rest_create_payload(config),
            )
            resource_name = live.get("name")
            target_runtime = resource_name
        metadata = verify_runtime_configuration(
            live,
            expected_gateway=args.agent_gateway,
            expected_image_uri=args.image_uri,
            expected_identity_type=args.identity_type,
        )
        result = deployment_result(metadata, deployed_at=datetime.now(UTC).isoformat())
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(resource_name)
    except Exception as exc:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(failure_evidence(gateway_id=args.agent_gateway, exc=exc, target_runtime=target_runtime), ensure_ascii=False, indent=2) + "\n")
        parser.exit(1, f"error: {json.dumps(safe_error(exc), ensure_ascii=False)}\n")


if __name__ == "__main__":
    main()
