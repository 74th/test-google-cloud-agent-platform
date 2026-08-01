"""Create a service-account-authenticated Vertex AI Agent Platform deployment."""

from __future__ import annotations

import argparse


VERTEX_HAIKU_MODEL = "claude-haiku-4-5@20251001"


def build_config(args: argparse.Namespace) -> dict[str, object]:
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
            "VERTEX_REGION_CLAUDE_HAIKU_4_5": "us-east5",
        },
        "class_methods": [
            {"name": "query", "api_mode": "", "parameters": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}},
            {"name": "stream_query", "api_mode": "stream", "parameters": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}},
        ],
        "service_account": args.service_account,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--image-uri", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--vertex-project", required=True)
    parser.add_argument("--vertex-region", required=True)
    parser.add_argument("--service-account", required=True)
    args = parser.parse_args()

    from google.cloud.aiplatform import vertexai

    client = vertexai.Client(project=args.project, location=args.location)
    remote_agent = client.agent_engines.create(config=build_config(args))
    print(remote_agent.api_resource.name)


if __name__ == "__main__":
    main()
