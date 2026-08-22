"""Agent Registry allow-list and Agent Gateway evidence commands."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY_FILE = ROOT / "terraform" / "egress-policy.yaml"
ESSENTIAL_GOOGLE_ENDPOINTS = {
    "agentregistry": "https://agentregistry.googleapis.com",
    "aiplatform": "https://us-central1-aiplatform.googleapis.com",
    "logging": "https://logging.googleapis.com",
}


def github_service_command(project: str, location: str, service: str) -> list[str]:
    return endpoint_service_command(project, location, service, "https://github.com", "20260822 GitHub egress endpoint")


def endpoint_service_command(project: str, location: str, service: str, url: str, display_name: str) -> list[str]:
    return [
        "gcloud",
        "agent-registry",
        "services",
        "create",
        service,
        f"--project={project}",
        f"--location={location}",
        f"--display-name={display_name}",
        "--endpoint-spec-type=no-spec",
        f'--interfaces=[{{"url":"{url}","protocolBinding":"http-json"}}]',
        "--format=value(registryResource)",
    ]


def allow_policy(principal: str) -> dict[str, Any]:
    if not principal.startswith("principal://"):
        raise ValueError("Agent identity principal は principal:// 形式で指定してください。")
    return {"bindings": [{"role": "roles/iap.egressor", "members": [principal]}]}


def collect_log_pages(fetch_page: Callable[[str | None], dict[str, Any]]) -> list[dict[str, Any]]:
    """Collect all pages from a Cloud Logging-like page-token API."""
    pages: list[dict[str, Any]] = []
    token: str | None = None
    while True:
        page = fetch_page(token)
        pages.extend(entry for entry in page.get("entries", []) if isinstance(entry, dict))
        token = page.get("nextPageToken")
        if not token:
            return pages


def run(command: list[str], *, output: Path | None = None) -> str:
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or "stderr は空でした。"
        raise RuntimeError(f"コマンドが終了コード {result.returncode} で失敗しました: {detail}")
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result.stdout, encoding="utf-8")
    return result.stdout


def register_github(project: str, location: str, service: str) -> str:
    return run(github_service_command(project, location, service))


def register_essential_google(project: str, location: str, service: str, url: str) -> str:
    return run(endpoint_service_command(project, location, service, url, f"20260822 managed {service}"))


def apply_allow_policy(project: str, location: str, endpoint_id: str, principal: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as handle:
        json.dump(allow_policy(principal), handle)
        handle.flush()
        run(
            [
                "gcloud",
                "iap",
                "web",
                "set-iam-policy",
                handle.name,
                f"--project={project}",
                "--resource-type=agent-registry",
                f"--endpoint={endpoint_id}",
                f"--region={location}",
                "--quiet",
            ]
        )


def gateway_export(project: str, location: str, gateway: str, output: Path) -> None:
    run(
        [
            "gcloud",
            "network-services",
            "agent-gateways",
            "describe",
            gateway,
            f"--project={project}",
            f"--location={location}",
            "--format=json",
        ],
        output=output,
    )


def logging_query(
    project: str,
    gateway: str,
    since: str | None = None,
    location: str | None = None,
) -> list[str]:
    query = (
        'resource.type="networkservices.googleapis.com/Gateway" '
        f'AND resource.labels.gateway_name="{gateway}"'
    )
    if location:
        query += f' AND resource.labels.location="{location}"'
    if since:
        query += f' AND timestamp>="{since}"'
    return [
        "gcloud",
        "logging",
        "read",
        query,
        f"--project={project}",
        "--format=json",
        "--order=asc",
    ]


def iap_logging_query(project: str, since: str | None = None) -> list[str]:
    query = 'protoPayload.serviceName="iap.googleapis.com" '
    if since:
        query += f'AND timestamp>="{since}" '
    return [
        "gcloud",
        "logging",
        "read",
        query,
        f"--project={project}",
        "--format=json",
        "--order=asc",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register-github")
    register.add_argument("--project", default=os.environ.get("PROJECT_ID", "nnyn-dev"))
    register.add_argument("--location", default=os.environ.get("LOCATION", "us-central1"))
    register.add_argument("--service", default="agw-20260822-github")
    managed = sub.add_parser("register-managed")
    managed.add_argument("--project", default=os.environ.get("PROJECT_ID", "nnyn-dev"))
    managed.add_argument("--location", default=os.environ.get("LOCATION", "us-central1"))
    managed.add_argument("--service", required=True)
    managed.add_argument("--url", required=True)
    allow = sub.add_parser("allow-github")
    allow.add_argument("--project", required=True)
    allow.add_argument("--location", required=True)
    allow.add_argument("--endpoint", required=True)
    allow.add_argument("--principal", required=True)
    export = sub.add_parser("export")
    export.add_argument("--project", required=True)
    export.add_argument("--location", required=True)
    export.add_argument("--gateway", required=True)
    export.add_argument("--output", type=Path, required=True)
    logs = sub.add_parser("logs")
    logs.add_argument("--project", required=True)
    logs.add_argument("--gateway", required=True)
    logs.add_argument("--location", default=os.environ.get("LOCATION", "us-central1"))
    logs.add_argument("--since")
    logs.add_argument("--output", type=Path)
    iap_logs = sub.add_parser("iap-logs")
    iap_logs.add_argument("--project", required=True)
    iap_logs.add_argument("--since")
    iap_logs.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "register-github":
        print(register_github(args.project, args.location, args.service), end="")
    elif args.command == "register-managed":
        print(register_essential_google(args.project, args.location, args.service, args.url), end="")
    elif args.command == "allow-github":
        apply_allow_policy(args.project, args.location, args.endpoint, args.principal)
    elif args.command == "export":
        gateway_export(args.project, args.location, args.gateway, args.output)
        print(args.output)
    elif args.command == "logs":
        print(run(logging_query(args.project, args.gateway, args.since, args.location), output=args.output), end="")
    else:
        print(run(iap_logging_query(args.project, args.since), output=args.output), end="")


if __name__ == "__main__":
    main()
