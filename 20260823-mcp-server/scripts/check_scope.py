#!/usr/bin/env python3
"""Fail closed when a migration plan leaves the consumer ownership boundary."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ALLOWED_ADDRESSES = (
    re.compile(r"^google_project_service\.required(?:\[.*\])?$"),
    re.compile(r"^google_artifact_registry_repository\.(mcp|agent_runtime)$"),
    re.compile(r"^google_artifact_registry_repository_iam_member\.agent_runtime_reader$"),
    re.compile(r"^google_cloud_run_v2_service\.mcp$"),
    re.compile(r"^google_cloud_run_v2_service_iam_member\.(test_invoker|mcp_caller)$"),
    re.compile(r"^google_service_account\.(cloud_run_runtime|test_invoker|mcp_caller|gke_node|gke_workload)$"),
    re.compile(r"^google_service_account_iam_member\.(caller_token_creator|gke_workload)$"),
    re.compile(
        r"^google_project_iam_member\.(registry_viewer|vertex_user|cloud_run_logs|gke_node_logs|gke_node_metrics|gke_node_artifacts)$"
    ),
    re.compile(r"^google_vertex_ai_reasoning_engine\.runtime$"),
    re.compile(r"^google_agent_registry_service\.(cloud_run|gke|agentregistry_control_plane|aiplatform_regional_control_plane|aiplatform_global_control_plane|iamcredentials_control_plane)$"),
    re.compile(r"^google_iap_agent_registry_endpoint_iam_member\.(agentregistry_control_plane|aiplatform_regional_control_plane|aiplatform_global_control_plane|iamcredentials_control_plane)$"),
    re.compile(r"^google_iap_agent_registry_mcp_server_iam_member\.(cloud_run|gke)$"),
    re.compile(r"^google_compute_network\.mcp$"),
    re.compile(r"^google_compute_subnetwork\.mcp$"),
    re.compile(r"^google_container_cluster\.mcp$"),
    re.compile(r"^google_container_node_pool\.mcp$"),
    re.compile(r"^google_compute_address\.gke_internal_https$"),
    re.compile(r"^google_compute_subnetwork\.gke_proxy_only$"),
    re.compile(r"^google_dns_managed_zone\.gke_private$"),
    re.compile(r"^google_dns_record_set\.gke_mcp$"),
)

FORBIDDEN = re.compile(
    r"(?:common-egress|common-agent-gateway-vpc|common-agent-gateway-subnet|common-agent-gateway-attachment|"
    r"autopilot|agw-20260822|20260822|claude-agent|allUsers|"
    r"google_network_services_agent_gateway|google_compute_network\.agent_gateway|"
    r"google_compute_network_attachment\.agent_gateway|google_compute_subnetwork\.agent_gateway)",
    re.IGNORECASE,
)

ALLOWED_API_SERVICES = {
    "agentregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "container.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "iap.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "networksecurity.googleapis.com",
    "networkservices.googleapis.com",
    "run.googleapis.com",
}


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in _strings(child)]
    return []


def _allowed(address: str, values: list[str]) -> bool:
    normalized_address = re.sub(r"\[[^\]]+\]$", "", address)
    if not any(pattern.fullmatch(normalized_address) for pattern in ALLOWED_ADDRESSES):
        return False
    if any(value.strip().lower() == "default" or "/networks/default" in value or "/subnetworks/default" in value for value in values):
        return False
    if address.startswith("google_project_service.required"):
        return any(service in values for service in ALLOWED_API_SERVICES)
    return any("mcp-20260823" in value for value in values) or normalized_address.startswith(
        "google_iap_agent_registry_"
    ) or normalized_address in {
        "google_artifact_registry_repository_iam_member.agent_runtime_reader",
        "google_project_iam_member.registry_viewer",
        "google_project_iam_member.vertex_user",
        "google_service_account_iam_member.caller_token_creator",
        "google_service_account_iam_member.gke_workload",
    }


def _scope_values(address: str, values: list[str]) -> list[str]:
    """Permit consumer resources to reference the shared VPC without managing it."""
    normalized_address = re.sub(r"\[[^\]]+\]$", "", address)
    if normalized_address in {
        "google_compute_subnetwork.mcp",
        "google_container_cluster.mcp",
        "google_dns_managed_zone.gke_private",
        "google_compute_subnetwork.gke_proxy_only",
    }:
        shared_network_values = {
            "common-agent-gateway-vpc",
            "projects/nnyn-dev/global/networks/common-agent-gateway-vpc",
            "https://www.googleapis.com/compute/v1/projects/nnyn-dev/global/networks/common-agent-gateway-vpc",
        }
        return [value for value in values if value not in shared_network_values]
    if normalized_address == "google_vertex_ai_reasoning_engine.runtime":
        return [value for value in values if value != "projects/nnyn-dev/locations/us-central1/agentGateways/common-egress"]
    return values


def check(plan: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for change in plan.get("resource_changes", []):
        address = change.get("address", "")
        actions = change.get("change", {}).get("actions", [])
        if not actions or actions == ["no-op"] or address.startswith("data."):
            continue
        values = _strings(change)
        joined = "\n".join(values)
        normalized_address = re.sub(r"\[[^\]]+\]$", "", address)
        scope_values = _scope_values(address, values)
        if FORBIDDEN.search("\n".join(scope_values)):
            failures.append(f"forbidden scope marker in {address}")
            continue
        if not _allowed(address, values):
            failures.append(f"unapproved managed resource action {address}: {','.join(actions)}")
    return failures


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} PLAN_JSON", file=sys.stderr)
        return 2
    try:
        plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"scope guard input error: {type(error).__name__}", file=sys.stderr)
        return 2
    failures = check(plan)
    if failures:
        for failure in failures:
            print(f"scope guard: REFUSE: {failure}", file=sys.stderr)
        return 1
    print("scope guard: PASS: consumer-only actions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
