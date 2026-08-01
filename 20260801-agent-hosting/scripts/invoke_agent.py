"""Authenticated local CLI for a deployed Agent Platform runtime."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request


def endpoint(agent_resource: str, location: str) -> str:
    if not agent_resource.startswith("projects/"):
        raise ValueError("--agent-resource は projects/.../reasoningEngines/... の完全名で指定してください。")
    return f"https://{location}-aiplatform.googleapis.com/v1/{agent_resource}/api/reasoning_engine"


def token() -> str:
    try:
        import google.auth
        from google.auth.transport.requests import Request

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        credentials.refresh(Request())
        if not credentials.token:
            raise RuntimeError("アクセストークンを取得できませんでした。")
        return credentials.token
    except Exception as exc:
        raise RuntimeError("Google Cloud ADC を取得できません。gcloud auth application-default login を実行してください。") from exc


def invoke(agent_resource: str, location: str, prompt: str) -> str:
    body = json.dumps({"class_method": "query", "input": {"message": prompt}}).encode()
    request = urllib.request.Request(endpoint(agent_resource, location), data=body, headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Agent Platform 呼び出しが HTTP {exc.code} で失敗しました。") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Agent Platform に接続できません。ロケーションとリソース名を確認してください。") from exc
    output = payload.get("output") if isinstance(payload, dict) else None
    if not isinstance(output, str) or not output.strip():
        raise RuntimeError("Agent Platform から有効なテキスト応答を受け取れませんでした。")
    return output.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--location", default=os.environ.get("LOCATION"))
    parser.add_argument("--agent-resource", default=os.environ.get("AGENT_RESOURCE"))
    parser.add_argument("prompt", nargs="?", default="次のバスは何時？")
    args = parser.parse_args()
    if not args.location or not args.agent_resource:
        parser.error("--location と --agent-resource（または LOCATION/AGENT_RESOURCE）が必要です。")
    try:
        print(invoke(args.agent_resource, args.location, args.prompt))
    except (RuntimeError, ValueError) as exc:
        parser.exit(1, f"エラー: {exc}\n")


if __name__ == "__main__":
    main()
