"""Run allow/deny validation and save correlated, non-secret evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

GITHUB_PROMPT = "https://github.com/74th の内容を要約して"
CAO_PROMPT = (
    "https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html は日本の国民の祝日についての広報ページだよ。"
    "この内容を見て、2027年の祝日を全て教えて。"
)


@dataclass(frozen=True)
class Case:
    name: str
    prompt: str
    expected_host: str
    expected_disposition: str


CASES = (
    Case("github", GITHUB_PROMPT, "github.com", "allow"),
    Case("cao-default-deny", CAO_PROMPT, "www8.cao.go.jp", "deny"),
)


def log_host_and_disposition(entry: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract a reviewable destination decision from Gateway or IAP logs."""
    direct_host = entry.get("host")
    direct_disposition = entry.get("disposition")
    if isinstance(direct_host, str) and isinstance(direct_disposition, str):
        return direct_host.split(":", 1)[0], direct_disposition.lower()

    payload = entry.get("jsonPayload") or {}
    security = payload.get("enforcedGatewaySecurityPolicy") or {}
    host = security.get("hostname")
    authz = payload.get("authzPolicyInfo") or {}
    authz_result = authz.get("result")
    if isinstance(host, str) and isinstance(authz_result, str):
        disposition = {"allowed": "allow", "denied": "deny"}.get(authz_result.lower())
        if disposition:
            return host.split(":", 1)[0], disposition
    rules = security.get("matchedRules") or []
    action = next(
        (rule.get("action") for rule in rules if isinstance(rule, dict) and rule.get("action")),
        None,
    )
    if isinstance(host, str) and isinstance(action, str):
        disposition = {"allowed": "allow", "denied": "deny"}.get(action.lower(), action.lower())
        return host.split(":", 1)[0], disposition

    request = (entry.get("protoPayload") or {}).get("request") or {}
    request_url = (request.get("httpRequest") or {}).get("url")
    granted = (entry.get("protoPayload") or {}).get("authorizationInfo") or []
    if isinstance(request_url, str):
        hostname = urlparse(request_url).hostname
        if hostname and granted and isinstance(granted[0], dict):
            return hostname, "allow" if granted[0].get("granted") else "deny"
    return None, None


def invoke_command(agent_resource: str, location: str, prompt: str) -> list[str]:
    if not agent_resource.startswith("projects/"):
        raise ValueError("agent_resource must be a full Reasoning Engine resource name")
    return [
        sys.executable,
        "scripts/invoke_agent.py",
        "--agent-resource",
        agent_resource,
        "--location",
        location,
        prompt,
    ]


def response_matches(case: Case, stdout: str) -> bool:
    """Check page-derived response semantics, not merely a non-empty response."""
    response = stdout.strip()
    if not response:
        return False
    lowered = response.casefold()
    if case.name == "github":
        return (
            "github" in lowered
            and "74th" in lowered
            and bool(re.search(r"[ぁ-んァ-ン一-龯]", response))
            and not any(marker in lowered for marker in ("取得できません", "取得に失敗", "アクセスできません"))
        )
    failure_markers = ("取得できません", "取得できず", "取得に失敗", "アクセスできません", "接続できません", "拒否")
    return bool(re.search("|".join(map(re.escape, failure_markers)), response)) and not re.search(
        r"(?:^|[\n、])\s*[-・]\s*\d{1,2}月\d{1,2}日", response
    )


def policy_allows_host(policy: dict[str, Any], host: str) -> bool:
    text = str(policy.get("text", ""))
    return re.search(rf"(?m)^\s*host:\s*{re.escape(host)}\s*$", text) is not None


def correlation_complete(result: dict[str, Any]) -> bool:
    required = ("verification_id", "caller", "runtime_effective_identity", "gateway_id", "started_at", "ended_at")
    return all(isinstance(result.get(field), str) and result[field] for field in required) and bool(
        result.get("application_fetch_log")
    )


def update_case_result(
    case: Case,
    evidence_dir: Path,
    result: dict[str, Any],
    logs: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    matched = []
    for entry in logs:
        host, disposition = log_host_and_disposition(entry)
        if host == case.expected_host and disposition == case.expected_disposition:
            matched.append(entry)
    result["matched_log_entries"] = matched
    result["gateway_decision"] = case.expected_disposition if matched else None
    result["policy_host_listed"] = policy_allows_host(policy, case.expected_host)
    result["correlation_complete"] = correlation_complete(result)
    if case.name == "cao-default-deny":
        result["default_deny_proven"] = (
            not result["policy_host_listed"]
            and result["gateway_decision"] == "deny"
            and result.get("expected_disposition") == "deny"
        )
    else:
        result["default_deny_proven"] = False
    result["passed"] = (
        result["exit_code"] == 0
        and response_matches(case, result["response"])
        and bool(matched)
        and result["correlation_complete"]
        and (case.name != "cao-default-deny" or result["default_deny_proven"])
    )
    (evidence_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def run_case(
    case: Case,
    evidence_dir: Path,
    invoke: Callable[[Case], tuple[int, str, str]],
    policy: dict[str, Any],
    logs: list[dict[str, Any]],
    context: dict[str, str] | None = None,
) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(UTC).isoformat()
    exit_code, stdout, stderr = invoke(case)
    ended_at = datetime.now(UTC).isoformat()
    (evidence_dir / "input.txt").write_text(case.prompt + "\n", encoding="utf-8")
    (evidence_dir / "response.txt").write_text(stdout, encoding="utf-8")
    (evidence_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    (evidence_dir / "application-fetch.log").write_text(stderr, encoding="utf-8")
    (evidence_dir / "exit-status").write_text(f"{exit_code}\n", encoding="utf-8")
    result = {
        "case": case.name,
        "prompt": case.prompt,
        "exit_code": exit_code,
        "expected_host": case.expected_host,
        "expected_disposition": case.expected_disposition,
        "response": stdout,
        "application_fetch_log": stderr,
        "started_at": started_at,
        "ended_at": ended_at,
    }
    if context:
        result.update(context)
    return update_case_result(case, evidence_dir, result, logs, policy)


def collect_live_logs(project: str, gateway: str, location: str, since: str) -> list[dict[str, Any]]:
    """Collect Gateway and IAP logs after the calls; retain a combined fixture API."""
    try:
        from scripts.gateway import iap_logging_query, logging_query, run
    except ModuleNotFoundError:
        from gateway import iap_logging_query, logging_query, run
    entries: list[dict[str, Any]] = []
    for command in (logging_query(project, gateway, since, location), iap_logging_query(project, since)):
        payload = json.loads(run(command))
        if isinstance(payload, list):
            entries.extend(entry for entry in payload if isinstance(entry, dict))
    return entries


def collect_application_logs(project: str, agent_resource: str, since: str) -> list[dict[str, Any]]:
    """Collect the Runtime's application stdout/stderr for the same window."""
    try:
        from scripts.gateway import run
    except ModuleNotFoundError:
        from gateway import run
    match = re.fullmatch(r"projects/[^/]+/locations/[^/]+/reasoningEngines/(?P<id>[^/]+)", agent_resource)
    if not match:
        raise ValueError("agent_resource must be a full Reasoning Engine resource name")
    query = (
        'resource.type="aiplatform.googleapis.com/ReasoningEngine" '
        f'AND resource.labels.reasoning_engine_id="{match.group("id")}" '
        f'AND timestamp>="{since}"'
    )
    payload = json.loads(run(["gcloud", "logging", "read", query, f"--project={project}", "--format=json", "--order=asc"]))
    return [entry for entry in payload if isinstance(entry, dict)] if isinstance(payload, list) else []


def application_entries_for_case(case: Case, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        entry for entry in entries
        if case.expected_host in str(entry.get("textPayload", ""))
    ]


def mcp_e2e_passed(evidence: dict[str, Any]) -> bool:
    """MCP E2E requires every independent execution layer."""
    required = (
        "registry_service_id",
        "interface_resolution",
        "selected_tool",
        "gateway_decision",
        "endpoint_authorization",
        "server_side_mcp_log",
    )
    return all(evidence.get(field) for field in required)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-resource", default=os.environ.get("AGENT_RESOURCE"))
    parser.add_argument("--location", default=os.environ.get("LOCATION", "us-central1"))
    parser.add_argument("--gateway-id", default=os.environ.get("AGENT_GATEWAY_ID"))
    parser.add_argument("--caller", default=os.environ.get("CALLER_IDENTITY"))
    parser.add_argument("--runtime-effective-identity", default=os.environ.get("RUNTIME_EFFECTIVE_IDENTITY"))
    parser.add_argument("--verification-id", default=os.environ.get("VERIFICATION_ID"))
    parser.add_argument("--evidence-root", type=Path, default=Path(os.environ.get("EVIDENCE_ROOT", "evidence")))
    parser.add_argument("--policy", type=Path, default=Path("terraform/egress-policy.yaml"))
    parser.add_argument("--logs", type=Path, help="JSON array of exported Gateway/IAP decision logs")
    parser.add_argument("--collect-after", action="store_true")
    parser.add_argument("--project")
    parser.add_argument("--gateway", help="short Gateway name for Cloud Logging filter")
    parser.add_argument("--since")
    args = parser.parse_args()
    if not args.agent_resource:
        parser.error("--agent-resource または AGENT_RESOURCE が必要です。")
    if not all((args.gateway_id, args.caller, args.runtime_effective_identity)):
        parser.error("--gateway-id、--caller、--runtime-effective-identity が必要です。")
    started_at = datetime.now(UTC)
    verification_id = args.verification_id or started_at.strftime("%Y%m%dT%H%M%SZ")
    root = args.evidence_root / verification_id
    policy_text = args.policy.read_text(encoding="utf-8")
    policy = {"text": policy_text}
    if args.collect_after and (not args.project or not args.gateway):
        parser.error("--collect-after には --project と --gateway が必要です。")
    logs = json.loads(args.logs.read_text(encoding="utf-8")) if args.logs else []
    context = {
        "verification_id": verification_id,
        "caller": args.caller,
        "runtime_effective_identity": args.runtime_effective_identity,
        "gateway_id": args.gateway_id,
    }

    def invoke(case: Case) -> tuple[int, str, str]:
        result = subprocess.run(
            invoke_command(args.agent_resource, args.location, case.prompt),
            check=False,
            text=True,
            capture_output=True,
        )
        return result.returncode, result.stdout, result.stderr

    results = [run_case(case, root / case.name, invoke, policy, logs, context) for case in CASES]
    application_logs: list[dict[str, Any]] = []
    if args.collect_after:
        logs = collect_live_logs(args.project, args.gateway, args.location, args.since or started_at.isoformat())
        application_logs = collect_application_logs(args.project, args.agent_resource, args.since or started_at.isoformat())
        for case, result in zip(CASES, results, strict=True):
            app_entries = application_entries_for_case(case, application_logs)
            result["application_fetch_log"] = app_entries
            (root / case.name / "application-fetch.log").write_text(
                json.dumps(app_entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        results = [update_case_result(case, root / case.name, result, logs, policy) for case, result in zip(CASES, results, strict=True)]
    (root / "policy.yaml").write_text(policy_text, encoding="utf-8")
    (root / "gateway-logs.json").write_text(json.dumps(logs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "iap-logs.json").write_text(json.dumps([entry for entry in logs if "protoPayload" in entry], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "application-logs.json").write_text(json.dumps(application_logs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "correlation.json").write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "timestamp": verification_id,
        "gateway_id": args.gateway_id,
        "caller": args.caller,
        "runtime_effective_identity": args.runtime_effective_identity,
        "results": results,
        "passed": all(result["passed"] for result in results),
        "mcp_e2e": "unproven",
        "constraints": ["Response-only assertions are insufficient.", "No destroy was run."],
    }
    (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(root)
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
