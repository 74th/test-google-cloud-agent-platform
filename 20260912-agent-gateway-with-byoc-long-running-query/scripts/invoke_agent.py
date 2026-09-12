"""Authenticated CLI for a deployed Agent Runtime's synchronous `query`.

Used for:
- Test case 2 (Gateway + short/synchronous query -- expected to work).
- The Gateway default-deny demonstration: ask the agent to summarize both
  https://github.com/74th (registered in Agent Registry, allowed) and
  https://www.tohoho-web.com/index.htm (not registered, expected denied).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.request
import re


RUNTIME_PATTERN = re.compile(r"^projects/[^/]+/locations/(?P<location>[^/]+)/reasoningEngines/[^/]+$")

DEFAULT_DENY_PROMPT = (
    "次の2つのURLを取得してください: "
    "https://github.com/74th https://www.tohoho-web.com/index.htm"
)


def endpoint(agent_resource: str, location: str, method: str = "query") -> str:
    match = RUNTIME_PATTERN.fullmatch(agent_resource or "")
    if not match or match.group("location") != location:
        raise ValueError("--agent-resource は指定 location の projects/.../reasoningEngines/... 完全名で指定してください。")
    if method not in {"query", "streamQuery"}:
        raise ValueError("method は query または streamQuery で指定してください。")
    return f"https://{location}-aiplatform.googleapis.com/v1/{agent_resource}:{method}"


def adc_token() -> str:
    import google.auth
    from google.auth.transport.requests import Request

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    if not credentials.token:
        raise RuntimeError("ADC token is empty")
    return credentials.token


def gcloud_token() -> str:
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        check=False,
        text=True,
        capture_output=True,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        raise RuntimeError("gcloud token is unavailable")
    return value


def token() -> str:
    """Use ADC first, then the active gcloud credential without persisting it."""
    try:
        return adc_token()
    except Exception:
        try:
            return gcloud_token()
        except Exception as exc:
            raise RuntimeError("Google Cloud ADC または gcloud 認証を取得できません。認証状態を確認してください。") from exc


def invoke(agent_resource: str, location: str, prompt: str) -> str:
    body = json.dumps({"class_method": "query", "input": {"message": prompt}}).encode()
    request = urllib.request.Request(
        endpoint(agent_resource, location),
        data=body,
        headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Agent Runtime 呼び出しが HTTP {exc.code} で失敗しました。") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Agent Runtime に接続できません。ロケーションとリソース名を確認してください。") from exc
    output = payload.get("output") if isinstance(payload, dict) else None
    if not isinstance(output, str) or not output.strip():
        raise RuntimeError("Agent Runtime から有効なテキスト応答を受け取れませんでした。")
    return output.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--location", default=os.environ.get("LOCATION"))
    parser.add_argument("--agent-resource", default=os.environ.get("AGENT_RESOURCE"))
    parser.add_argument("--default-deny-check", action="store_true",
                        help="github.com (許可) と tohoho-web.com (未登録=default-deny) の要約を依頼する")
    parser.add_argument("prompt", nargs="?", default=None)
    args = parser.parse_args()
    if not args.location or not args.agent_resource:
        parser.error("--location と --agent-resource（または LOCATION/AGENT_RESOURCE）が必要です。")
    prompt = DEFAULT_DENY_PROMPT if args.default_deny_check else (args.prompt or "https://github.com/74th を取得して")
    try:
        print(invoke(args.agent_resource, args.location, prompt))
    except (RuntimeError, ValueError) as exc:
        parser.exit(1, f"エラー: {exc}\n")


if __name__ == "__main__":
    main()
