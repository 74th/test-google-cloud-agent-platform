#!/usr/bin/env python3
"""Run a bounded Agent Runtime probe and emit only sanitized evidence fields."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


SECRET_KEY = re.compile(r"authorization|token|certificate|private.?key|credential|secret|password|cookie", re.I)
SECRET_VALUE = re.compile(
    r"Bearer\s+\S+|-----BEGIN [^-]+-----.*?-----END [^-]+-----|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
    re.I | re.S,
)


def sanitize(value: Any, key: str = "") -> Any:
    if SECRET_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {name: sanitize(child, name) for name, child in value.items() if not SECRET_KEY.search(name)}
    if isinstance(value, list):
        return [sanitize(child, key) for child in value]
    if isinstance(value, str):
        return SECRET_VALUE.sub("[REDACTED]", value)
    return value


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def run_runtime_query(args: argparse.Namespace, probe_id: str) -> dict[str, Any]:
    query_url = (
        f"https://us-central1-aiplatform.googleapis.com/v1/projects/{args.runtime_project}"
        f"/locations/{args.runtime_location}/reasoningEngines/{args.runtime_id}:query"
    )
    payload = {
        "class_method": "query",
        "input": {
            "target": args.target,
            "message": "execute the registered validation tool once",
            "correlation_id": probe_id,
        },
    }
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
        request = urllib.request.Request(
            query_url,
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            body = response.read(1024 * 1024).decode(errors="replace")
            parsed: Any
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"body": body}
            return {"http_status": response.status, "response": sanitize(parsed)}
    except urllib.error.HTTPError as exc:
        body = exc.read(1024 * 1024).decode(errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"body": body}
        return {"http_status": exc.code, "response": sanitize(parsed)}
    except Exception as exc:  # pragma: no cover - environment-specific failures
        return {"error_type": type(exc).__name__, "error": sanitize(str(exc))}


def read_gateway_logs(args: argparse.Namespace, start: dt.datetime, end: dt.datetime) -> dict[str, Any]:
    log_filter = (
        f'logName="projects/{args.gateway_project}/logs/networkservices.googleapis.com%2Fgateway_requests" '
        f'AND timestamp >= "{start.isoformat().replace("+00:00", "Z")}" '
        f'AND timestamp <= "{end.isoformat().replace("+00:00", "Z")}"'
    )
    try:
        raw = subprocess.check_output(
            [
                "gcloud", "logging", "read", log_filter,
                f"--project={args.gateway_project}", "--limit=50", "--format=json",
            ],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=args.timeout,
        )
        entries = []
        for entry in json.loads(raw):
            resource_labels = (entry.get("resource") or {}).get("labels") or {}
            http_request = entry.get("httpRequest") or {}
            payload = entry.get("jsonPayload") or {}
            policy = payload.get("enforcedGatewaySecurityPolicy") or {}
            mtls = payload.get("mtls") or {}
            entries.append(
                {
                    "timestamp": entry.get("timestamp"),
                    "gateway": resource_labels.get("gateway_name"),
                    "source_project": resource_labels.get("resource_container"),
                    "method": http_request.get("requestMethod"),
                    "protocol": http_request.get("protocol"),
                    "status": http_request.get("status"),
                    "hostname": policy.get("hostname"),
                    "matched_rules": policy.get("matchedRules"),
                    "mtls_client_chain_verified": mtls.get("clientCertChainVerified"),
                }
            )
        return {"query": log_filter, "entries": sanitize(entries)}
    except Exception as exc:  # pragma: no cover - environment-specific failures
        return {"query": log_filter, "error_type": type(exc).__name__, "error": sanitize(str(exc))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-project", default="776113568960")
    parser.add_argument("--runtime-location", default="us-central1")
    parser.add_argument("--runtime-id", default="2332905838663958528")
    parser.add_argument("--registry-service", default="mcp-20260823-gke")
    parser.add_argument("--target", default="gke")
    parser.add_argument("--gateway-project", default="nnyn-dev")
    parser.add_argument("--gateway-id", default="projects/nnyn-dev/locations/us-central1/agentGateways/common-egress")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    start = utc_now()
    probe_id = str(uuid.uuid4())
    evidence: dict[str, Any] = {
        "probe_id": probe_id,
        "window_start_utc": start.isoformat().replace("+00:00", "Z"),
        "caller": "operator ADC" if not args.dry_run else "dry-run fixture",
        "runtime": {
            "project": args.runtime_project,
            "location": args.runtime_location,
            "id": args.runtime_id,
            "target_registry_service": args.registry_service,
        },
        "gateway": {"project": args.gateway_project, "id": args.gateway_id},
        "credential_persistence": "none",
    }
    if args.dry_run:
        evidence["runtime_result"] = {"mode": "dry-run", "request_not_sent": True}
        evidence["gateway_logs"] = {"mode": "dry-run", "query_not_sent": True}
    else:
        evidence["runtime_result"] = run_runtime_query(args, probe_id)
        end = utc_now()
        evidence["window_end_utc"] = end.isoformat().replace("+00:00", "Z")
        # Managed Gateway logs can arrive a few seconds after the Runtime response.
        evidence["gateway_logs"] = read_gateway_logs(args, start, end + dt.timedelta(seconds=15))
    evidence = sanitize(evidence)
    encoded = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded)
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
