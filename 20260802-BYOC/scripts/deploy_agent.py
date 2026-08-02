"""Create a BYOC agent and persist its resource name and operation schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CLASS_METHODS = [
    {"name": "query", "api_mode": "", "parameters": {"type": "object", "properties": {"verification_id": {"type": "string"}}, "required": ["verification_id"]}},
    {"name": "async_query", "api_mode": "async", "parameters": {"type": "object", "properties": {"verification_id": {"type": "string"}}, "required": ["verification_id"]}},
    {"name": "stream_query", "api_mode": "stream", "parameters": {"type": "object", "properties": {"verification_id": {"type": "string"}}, "required": ["verification_id"]}},
    {"name": "async_stream_query", "api_mode": "async_stream", "parameters": {"type": "object", "properties": {"verification_id": {"type": "string"}}, "required": ["verification_id"]}},
]


def build_config(args: argparse.Namespace) -> dict[str, object]:
    return {"display_name": args.display_name, "agent_framework": "custom", "container_spec": {"image_uri": args.image_uri}, "class_methods": CLASS_METHODS, "service_account": args.service_account}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True); parser.add_argument("--location", required=True)
    parser.add_argument("--image-uri", required=True); parser.add_argument("--service-account", required=True)
    parser.add_argument("--display-name", default="byoc-query-verification")
    parser.add_argument("--result", type=Path, default=Path("results/deployment.json"))
    args = parser.parse_args()
    import agentplatform
    remote = agentplatform.Client(project=args.project, location=args.location).agent_engines.create(config=build_config(args))
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps({"resource_name": remote.api_resource.name, "operation_schemas": remote.operation_schemas()}, default=str, ensure_ascii=False, indent=2) + "\n")
    print(remote.api_resource.name)


if __name__ == "__main__": main()
