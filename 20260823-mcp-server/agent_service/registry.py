from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import asdict
from typing import Any, Protocol
from urllib.parse import quote, urlparse

from .errors import Stage, ValidationError
from .models import RegistryEntry, TargetConfig


class RegistryClient(Protocol):
    def describe(self, project: str, location: str, service_id: str) -> dict[str, Any]: ...


class GcloudRegistryClient:
    """Resolve Registry metadata through the Agent Registry REST surface.

    The name is retained for the local compatibility surface, but the hosted
    Runtime image intentionally does not depend on the gcloud CLI.
    """

    def __init__(self, runner: Callable[..., subprocess.CompletedProcess[str]] | None = None):
        self._runner = runner

    def describe(self, project: str, location: str, service_id: str) -> dict[str, Any]:
        try:
            if self._runner is not None:
                result = self._runner(
                    [
                        "gcloud",
                        "agent-registry",
                        "services",
                        "describe",
                        service_id,
                        f"--project={project}",
                        f"--location={location}",
                        "--format=json",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return json.loads(result.stdout)

            import google.auth
            from google.auth.transport.requests import AuthorizedSession

            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            resource = "/".join(
                [
                    "v1",
                    "projects",
                    quote(project, safe=""),
                    "locations",
                    quote(location, safe=""),
                    "services",
                    quote(service_id, safe=""),
                ]
            )
            response = AuthorizedSession(credentials).get(f"https://agentregistry.googleapis.com/{resource}", timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            detail = f"HTTP {status}" if status is not None else type(error).__name__
            raise ValidationError(Stage.REGISTRY_DISCOVERY, f"Registry service lookup failed ({detail})") from error


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _find_tools(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        for key in ("tools", "toolDefinitions"):
            if isinstance(value.get(key), list):
                return [item for item in value[key] if isinstance(item, dict)]
        for child in value.values():
            result = _find_tools(child)
            if result:
                return result
    elif isinstance(value, list):
        for child in value:
            result = _find_tools(child)
            if result:
                return result
    return []


def _canonical_tool(tool: dict[str, Any]) -> dict[str, Any]:
    schema = _first(tool, "inputSchema", "input_schema") or {}
    return {
        "name": tool.get("name"),
        "description": tool.get("description"),
        "inputSchema": schema,
    }


def _service_id_from_name(name: Any) -> str | None:
    if not isinstance(name, str):
        return None
    match = re.fullmatch(r"projects/[^/]+/locations/[^/]+/services/([^/]+)", name)
    return match.group(1) if match else None


class RegistryResolver:
    """Resolve and validate a fixed target; never accepts a runtime URL."""

    def __init__(
        self,
        client: RegistryClient,
        project: str,
        location: str,
        targets: dict[str, TargetConfig],
        expected_tools: dict[str, dict[str, Any]],
    ):
        self.client = client
        self.project = project
        self.location = location
        self.targets = targets
        self.expected_tools = expected_tools

    def resolve(self, target: str, *, requested_url: str | None = None) -> RegistryEntry:
        if requested_url is not None:
            raise ValidationError(Stage.METADATA_VALIDATION, "runtime endpoint URLs are not accepted")
        config = self.targets.get(target)
        if config is None:
            raise ValidationError(Stage.REGISTRY_DISCOVERY, "unknown validation target")
        try:
            service = self.client.describe(self.project, self.location, config.service_id)
        except ValidationError:
            raise
        except Exception as error:
            raise ValidationError(Stage.REGISTRY_DISCOVERY, "Registry service lookup failed") from error
        return self._validate(config, service)

    def _validate(self, config: TargetConfig, service: dict[str, Any]) -> RegistryEntry:
        try:
            expected_name = f"projects/{self.project}/locations/{self.location}/services/{config.service_id}"
            if service.get("name") != expected_name or _service_id_from_name(service.get("name")) != config.service_id:
                raise ValueError("service identity mismatch")
            interfaces = service.get("interfaces") or []
            if len(interfaces) != 1:
                raise ValueError("expected exactly one interface")
            interface = interfaces[0]
            url = _first(interface, "url")
            binding = _first(interface, "protocolBinding", "protocol_binding")
            parsed = urlparse(url or "")
            if parsed.scheme not in config.allowed_schemes:
                schemes = ", ".join(sorted(config.allowed_schemes))
                raise ValueError(f"interface scheme must be one of: {schemes}")
            if parsed.hostname not in config.allowed_hosts:
                raise ValueError("interface host is not allowlisted")
            if binding != "JSONRPC":
                raise ValueError("interface must use JSONRPC")
            tools = _find_tools(service)
            expected = self.expected_tools[config.name]
            matching = [_canonical_tool(tool) for tool in tools if tool.get("name") == expected.get("name")]
            if matching != [_canonical_tool(expected)]:
                raise ValueError("registered Tool schema does not match")
            return RegistryEntry(
                target=config.name,
                project=self.project,
                location=self.location,
                service_id=config.service_id,
                endpoint_id=_first(service, "registryResource", "endpointId"),
                url=url,
                host=parsed.hostname or "",
                protocol_binding=binding,
                tool=expected,
                audience=config.audience,
            )
        except ValidationError:
            raise
        except Exception as error:
            raise ValidationError(Stage.METADATA_VALIDATION, "Registry metadata validation failed") from error

    def configured_targets(self) -> dict[str, dict[str, Any]]:
        return {name: asdict(config) for name, config in self.targets.items()}
