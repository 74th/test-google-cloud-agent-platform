#!/usr/bin/env python3
"""Validate a shared Agent Gateway owner output against a live API response."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_GATEWAY_ID = "projects/nnyn-dev/locations/us-central1/agentGateways/common-egress"
ID_PATTERN = re.compile(r"^projects/([^/]+)/locations/([^/]+)/agentGateways/([^/]+)$")


def _load(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read JSON input ({type(error).__name__})") from error
    if not isinstance(value, dict):
        raise ValueError("JSON input must be an object")
    return value


def _owner_id(owner: dict[str, Any]) -> str | None:
    value = owner.get("agent_gateway_id")
    if isinstance(value, str):
        return value
    output = owner.get("agent_gateway_id")
    if isinstance(output, dict) and isinstance(output.get("value"), str):
        return output["value"]
    return None


def _active_check(live: dict[str, Any]) -> str | None:
    # The current Agent Gateway GET surface omits a state field. If a future
    # response or a fixture provides one, fail closed for every non-active
    # state. A pending long-running operation is also not deployable.
    state = live.get("state") or live.get("status")
    if state is not None and str(state).upper() not in {"ACTIVE", "READY", "RUNNING"}:
        return f"live Gateway is not active ({state})"
    operation = live.get("operation")
    if isinstance(operation, dict) and operation.get("done") is False:
        return "live Gateway operation is still running"
    if live.get("deleteTime") or live.get("deletionTime"):
        return "live Gateway is being deleted"
    return None


def validate(owner: dict[str, Any], live: dict[str, Any], required_id: str) -> dict[str, Any]:
    expected_match = ID_PATTERN.fullmatch(required_id)
    if not expected_match:
        raise ValueError("required Gateway ID must be fully qualified")
    owner_id = _owner_id(owner)
    live_id = live.get("name")
    if owner_id != required_id:
        raise ValueError(f"owner output Gateway mismatch: {owner_id or 'missing'}")
    if live_id != required_id:
        raise ValueError(f"live Gateway mismatch: {live_id or 'missing'}")
    if _active_check(live):
        raise ValueError(_active_check(live) or "live Gateway is not active")

    project, location, _ = expected_match.groups()
    if live.get("googleManaged", {}).get("governedAccessPath") != "AGENT_TO_ANYWHERE":
        raise ValueError("governed access path mismatch")
    if "MCP" not in (live.get("protocols") or []):
        raise ValueError("MCP protocol is not enabled")
    expected_registry = f"//agentregistry.googleapis.com/projects/{project}/locations/{location}"
    if expected_registry not in (live.get("registries") or []):
        raise ValueError("Registry path mismatch")
    expected_attachment = (
        f"https://www.googleapis.com/compute/v1/projects/{project}/regions/{location}/networkAttachments/"
        "common-agent-gateway-attachment"
    )
    attachment = live.get("networkConfig", {}).get("egress", {}).get("networkAttachment")
    if attachment != expected_attachment:
        raise ValueError("Network Attachment mismatch")

    roots = live.get("agentGatewayCard", {}).get("rootCertificates")
    return {
        "status": "PASS",
        "agent_gateway_id": required_id,
        "project": project,
        "location": location,
        "governed_access_path": "AGENT_TO_ANYWHERE",
        "protocol": "MCP",
        "registry": expected_registry,
        "network_attachment": attachment,
        "root_certificate_count": len(roots) if isinstance(roots, list) else 0,
        "etag": live.get("etag"),
        "active_evidence": "live GET/list succeeded and no non-active state/operation was returned",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-json", required=True)
    parser.add_argument("--live-json", required=True)
    parser.add_argument("--required-id", default=DEFAULT_GATEWAY_ID)
    args = parser.parse_args()
    try:
        result = validate(_load(args.owner_json), _load(args.live_json), args.required_id)
    except ValueError as error:
        print(f"gateway preflight: REFUSE: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
