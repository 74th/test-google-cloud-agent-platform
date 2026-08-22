"""Run the two live prompts and save independently reviewable evidence."""

from __future__ import annotations

import argparse
import json
import os
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
        return direct_host, direct_disposition.lower()

    payload = entry.get("jsonPayload") or {}
    security = payload.get("enforcedGatewaySecurityPolicy") or {}
    host = security.get("hostname")
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
    return [
        sys.executable,
        "scripts/invoke_agent.py",
        "--agent-resource",
        agent_resource,
        "--location",
        location,
        prompt,
    ]


def run_case(
    case: Case,
    evidence_dir: Path,
    invoke: Callable[[Case], tuple[int, str, str]],
    policy: dict[str, Any],
    logs: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    exit_code, stdout, stderr = invoke(case)
    (evidence_dir / "input.txt").write_text(case.prompt + "\n", encoding="utf-8")
    (evidence_dir / "response.txt").write_text(stdout, encoding="utf-8")
    (evidence_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    (evidence_dir / "exit-status").write_text(f"{exit_code}\n", encoding="utf-8")
    matched = []
    for entry in logs:
        host, disposition = log_host_and_disposition(entry)
        if host == case.expected_host and disposition == case.expected_disposition:
            matched.append(entry)
    response_ok = bool(stdout.strip()) and (case.name == "github" or "取得" in stdout or "接続" in stdout or "拒否" in stdout)
    passed = exit_code == 0 and response_ok and bool(matched)
    result = {
        "case": case.name,
        "prompt": case.prompt,
        "exit_code": exit_code,
        "expected_host": case.expected_host,
        "expected_disposition": case.expected_disposition,
        "matched_log_entries": matched,
        "passed": passed,
    }
    (evidence_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-resource", default=os.environ.get("AGENT_RESOURCE"))
    parser.add_argument("--location", default=os.environ.get("LOCATION", "us-central1"))
    parser.add_argument("--evidence-root", type=Path, default=Path(os.environ.get("EVIDENCE_ROOT", "evidence")))
    parser.add_argument("--policy", type=Path, default=Path("terraform/egress-policy.yaml"))
    parser.add_argument("--logs", type=Path, help="JSON array of exported gateway decision logs")
    args = parser.parse_args()
    if not args.agent_resource:
        parser.error("--agent-resource または AGENT_RESOURCE が必要です。")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    root = args.evidence_root / timestamp
    policy_text = args.policy.read_text(encoding="utf-8")
    policy = {"text": policy_text}
    logs = json.loads(args.logs.read_text(encoding="utf-8")) if args.logs else []

    def invoke(case: Case) -> tuple[int, str, str]:
        result = subprocess.run(
            invoke_command(args.agent_resource, args.location, case.prompt),
            check=False,
            text=True,
            capture_output=True,
        )
        return result.returncode, result.stdout, result.stderr

    results = [run_case(case, root / case.name, invoke, policy, logs) for case in CASES]
    (root / "policy.yaml").write_text(policy_text, encoding="utf-8")
    (root / "gateway-logs.json").write_text(json.dumps(logs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "timestamp": timestamp,
        "results": results,
        "passed": all(result["passed"] for result in results),
        "constraints": ["Evidence records are not a substitute for inspecting gateway logs.", "No destroy was run."],
    }
    (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(root)
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
