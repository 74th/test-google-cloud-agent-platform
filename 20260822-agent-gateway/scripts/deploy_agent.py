"""Create a custom-container Agent Runtime and bind it to Agent Gateway."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from typing import Any

VERTEX_HAIKU_MODEL = "claude-haiku-4-5@20251001"


def build_config(args: argparse.Namespace) -> dict[str, object]:
    """Build the Agent Runtime create payload without credentials."""
    return {
        "display_name": args.display_name,
        "agent_framework": "custom",
        "container_spec": {"image_uri": args.image_uri},
        "env_vars": {
            "CLAUDE_CODE_USE_VERTEX": "1",
            "ANTHROPIC_VERTEX_PROJECT_ID": args.vertex_project,
            "CLOUD_ML_REGION": args.vertex_region,
            "ANTHROPIC_MODEL": VERTEX_HAIKU_MODEL,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": VERTEX_HAIKU_MODEL,
            "VERTEX_REGION_CLAUDE_HAIKU_4_5": "global",
        },
        "class_methods": [
            {
                "name": "query",
                "api_mode": "",
                "parameters": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
            },
            {
                "name": "stream_query",
                "api_mode": "stream",
                "parameters": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
            },
        ],
        "service_account": args.service_account,
        "identity_type": "AGENT_IDENTITY",
    }


def gateway_patch(agent_resource: str, gateway_resource: str) -> dict[str, Any]:
    return {
        "spec": {
            "deploymentSpec": {
                "agentGatewayConfig": {
                    "agentToAnywhereConfig": {"agentGateway": gateway_resource}
                }
            }
        }
    }


def patch_gateway(agent_resource: str, location: str, gateway_resource: str) -> None:
    from google.auth.transport.requests import Request
    import google.auth

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    url = f"https://{location}-aiplatform.googleapis.com/v1/{agent_resource}"
    body = json.dumps(gateway_patch(agent_resource, gateway_resource)).encode()
    request = urllib.request.Request(
        f"{url}?updateMask=spec.deploymentSpec.agentGatewayConfig",
        data=body,
        headers={"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(request, timeout=120):
            return
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Agent Gateway への関連付けが HTTP {exc.code} で失敗しました。") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--image-uri", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--vertex-project", required=True)
    parser.add_argument("--vertex-region", required=True)
    parser.add_argument("--service-account", required=True)
    parser.add_argument("--agent-gateway", required=True)
    args = parser.parse_args()

    try:
        import vertexai

        client = vertexai.Client(project=args.project, location=args.location)
        config = build_config(args)
        # Agent Gateway requires Agent Identity. The Vertex API rejects a
        # service_account field together with AGENT_IDENTITY; the Terraform
        # service account remains managed for the non-identity IAM contract.
        config.pop("service_account", None)
        remote = client.agent_engines.create(config=config)
        api_resource = getattr(remote, "api_resource", None)
        resource = (
            getattr(remote, "name", None)
            or getattr(remote, "resource_name", None)
            or getattr(api_resource, "name", None)
        )
        if not isinstance(resource, str) or not resource.startswith("projects/"):
            raise RuntimeError("Agent Runtime の完全なリソース名を取得できませんでした。")
        patch_gateway(resource, args.location, args.agent_gateway)
        print(resource)
    except Exception as exc:
        raise SystemExit(f"エージェントの作成に失敗しました: {exc}") from exc


if __name__ == "__main__":
    main()
