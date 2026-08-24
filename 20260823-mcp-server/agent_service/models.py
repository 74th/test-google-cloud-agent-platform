from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TargetConfig:
    name: str
    service_id: str
    allowed_hosts: frozenset[str]
    audience: str
    tool_name: str = "validate_echo"


@dataclass(frozen=True)
class RegistryEntry:
    target: str
    project: str
    location: str
    service_id: str
    endpoint_id: str | None
    url: str
    host: str
    protocol_binding: str
    tool: dict[str, Any]
    audience: str


@dataclass
class InvocationEvidence:
    correlation_id: str
    target: str
    service_id: str | None = None
    endpoint_id: str | None = None
    validated_host: str | None = None
    identity_chain: list[str] = field(default_factory=list)
    sdk_tool_events: list[dict[str, str]] = field(default_factory=list)
    final_response: str | None = None
    log_references: list[str] = field(default_factory=list)

    def sanitized(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "target": self.target,
            "service_id": self.service_id,
            "endpoint_id": self.endpoint_id,
            "validated_host": self.validated_host,
            "identity_chain": self.identity_chain,
            "sdk_tool_events": self.sdk_tool_events,
            "final_response": self.final_response,
            "log_references": self.log_references,
        }
