#!/usr/bin/env python3
"""Fail closed on Terraform plans outside the common Gateway boundary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROTECTED_TYPES = {
    "google_compute_network",
    "google_compute_subnetwork",
    "google_compute_network_attachment",
    "google_network_services_agent_gateway",
}

AUTHZ_EXTENSION_TYPE = "google_network_services_authz_extension"
AUTHZ_POLICY_TYPE = "google_network_security_authz_policy"
COMMON_TYPES = PROTECTED_TYPES | {"google_project_service", AUTHZ_EXTENSION_TYPE, AUTHZ_POLICY_TYPE}
FORBIDDEN_TYPE_MARKERS = (
    "google_container_",
    "google_cloud_run_",
    "google_vertex_ai_",
    "google_agent_registry_",
    "google_iap_",
    "google_artifact_registry_",
)
FORBIDDEN_STRINGS = (
    "allusers",
    "roles/owner",
    "roles/editor",
    "0.0.0.0/0",
    "::/0",
    "bearer ",
    "-----begin ",
)
# Network Security normalizes AuthzPolicy target references to the owning
# project number on read-back. Keep the mapping deliberately bounded rather
# than accepting arbitrary numeric project paths.
PROJECT_NUMBERS = {"nnyn-dev": "776113568960"}


def flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in flatten_strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in flatten_strings(child)]
    return []


def keyed_values(value: Any, key: str = "") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(key, value)]
    if isinstance(value, dict):
        return [item for name, child in value.items() for item in keyed_values(child, name)]
    if isinstance(value, list):
        return [item for child in value for item in keyed_values(child, key)]
    return []


def resource_project(resource: dict[str, Any]) -> str | None:
    for body_key in ("change",):
        body = resource.get(body_key, {})
        for value_key in ("after", "before"):
            body_value = body.get(value_key)
            if isinstance(body_value, dict) and body_value.get("project"):
                return body_value["project"]
    return None


def validate(plan: dict[str, Any], expected_project: str, expected_region: str, gateway_name: str) -> list[str]:
    errors: list[str] = []
    changes = plan.get("resource_changes")
    if not isinstance(changes, list):
        return ["plan JSON has no resource_changes list"]

    for resource in changes:
        address = resource.get("address", "<unknown>")
        resource_type = resource.get("type", "")
        actions = resource.get("change", {}).get("actions", [])
        after = resource.get("change", {}).get("after") or {}
        before = resource.get("change", {}).get("before") or {}
        body = after if after else before

        if any(marker in resource_type for marker in FORBIDDEN_TYPE_MARKERS):
            errors.append(f"{address}: consumer-owned resource type is out of scope ({resource_type})")

        if resource_type not in COMMON_TYPES:
            errors.append(f"{address}: resource type is outside the common allowlist ({resource_type})")

        if resource_type in PROTECTED_TYPES and any(action in actions for action in ("delete", "replace")):
            errors.append(f"{address}: protected common resource may not be deleted or replaced ({actions})")

        if resource_type == "google_network_services_agent_gateway":
            name = body.get("name")
            if name and name not in (gateway_name, f"projects/{expected_project}/locations/{expected_region}/agentGateways/{gateway_name}"):
                errors.append(f"{address}: unexpected Gateway name {name!r}")
            location = body.get("location")
            if location and location != expected_region:
                errors.append(f"{address}: Gateway location is outside {expected_region}: {location!r}")

        if resource_type == AUTHZ_EXTENSION_TYPE:
            if body.get("name") != "common-egress-iap-authz":
                errors.append(f"{address}: unexpected Authz Extension name {body.get('name')!r}")
            if body.get("location") != expected_region:
                errors.append(f"{address}: Authz Extension location is outside {expected_region}")
            if body.get("service") != "iap.googleapis.com":
                errors.append(f"{address}: Authz Extension must use iap.googleapis.com")
            if body.get("fail_open") is not True:
                errors.append(f"{address}: Authz Extension must remain fail_open during DRY_RUN")
            metadata = body.get("metadata") or {}
            if metadata != {"iamEnforcementMode": "DRY_RUN", "iapPolicyVersion": "V1"}:
                errors.append(f"{address}: Authz Extension metadata must remain the approved DRY_RUN IAP configuration")

        if resource_type == AUTHZ_POLICY_TYPE:
            if body.get("name") != "common-egress-iap-policy":
                errors.append(f"{address}: unexpected AuthzPolicy name {body.get('name')!r}")
            if body.get("location") != expected_region:
                errors.append(f"{address}: AuthzPolicy location is outside {expected_region}")
            if body.get("policy_profile") != "REQUEST_AUTHZ" or body.get("action") != "CUSTOM":
                errors.append(f"{address}: AuthzPolicy must remain REQUEST_AUTHZ/CUSTOM")
            target = body.get("target") or []
            expected_gateway = f"projects/{expected_project}/locations/{expected_region}/agentGateways/{gateway_name}"
            expected_gateway_number = f"projects/{PROJECT_NUMBERS.get(expected_project, expected_project)}/locations/{expected_region}/agentGateways/{gateway_name}"
            if len(target) != 1 or target[0].get("resources") not in ([expected_gateway], [expected_gateway_number]):
                errors.append(f"{address}: AuthzPolicy must target only {expected_gateway}")
            provider = body.get("custom_provider") or []
            expected_extension = f"projects/{expected_project}/locations/{expected_region}/authzExtensions/common-egress-iap-authz"
            expected_extension_number = f"projects/{PROJECT_NUMBERS.get(expected_project, expected_project)}/locations/{expected_region}/authzExtensions/common-egress-iap-authz"
            try:
                extensions = provider[0]["authz_extension"][0]["resources"]
            except (IndexError, KeyError, TypeError):
                extensions = []
            unknown_extension = (
                resource.get("change", {})
                .get("after_unknown", {})
                .get("custom_provider", [{}])[0]
                .get("authz_extension", [{}])[0]
                .get("resources")
                is True
            )
            # A newly-created extension ID is unknown in Terraform's saved
            # plan. The HCL/static test fixes its source; only this precise
            # unknown is accepted until post-apply read-back can prove it.
            if extensions not in ([expected_extension], [expected_extension_number]) and not (extensions == [] and unknown_extension):
                errors.append(f"{address}: AuthzPolicy must reference only {expected_extension}")

        project = resource_project(resource)
        if project and project not in (expected_project, str(expected_project)):
            errors.append(f"{address}: project is outside {expected_project}: {project!r}")

        if resource_type == "google_project_service":
            service = body.get("service")
            if service not in {
                "agentregistry.googleapis.com",
                "compute.googleapis.com",
                "networksecurity.googleapis.com",
                "networkservices.googleapis.com",
                "serviceusage.googleapis.com",
            }:
                errors.append(f"{address}: unexpected API enablement {service!r}")

        for key, value in keyed_values(body):
            key_lower = key.lower()
            # The Gateway API returns its inspection CA as an output-only plan
            # value. Never print or inspect its body as an authorization tuple.
            if key_lower in {"root_certificates", "certificate", "private_key"}:
                continue
            value_lower = value.lower()
            if any(forbidden in value_lower for forbidden in FORBIDDEN_STRINGS):
                errors.append(f"{address}: unsafe broad/secret-like value detected")
            if key_lower in {"hosts", "host", "principals", "principal", "members", "member"}:
                if value.strip().lower() in {"*", "", "any", "all"}:
                    errors.append(f"{address}: wildcard or empty authorization value is not allowed")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan_json", type=Path)
    parser.add_argument("--project", default="nnyn-dev")
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--gateway", default="common-egress")
    args = parser.parse_args()

    try:
        plan = json.loads(args.plan_json.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"scope guard: unable to read plan JSON: {exc}", file=sys.stderr)
        return 2

    errors = validate(plan, args.project, args.region, args.gateway)
    if errors:
        print("scope guard: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"scope guard: PASS: {args.project}/{args.region}, Gateway {args.gateway}; no protected delete/replace")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
