"""Delete an Agent Platform deployment by its full resource name."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--agent-resource", required=True)
    args = parser.parse_args()
    from google.cloud.aiplatform import vertexai

    vertexai.Client(project=args.project, location=args.location).agent_engines.delete(name=args.agent_resource)
    print(f"削除を要求しました: {args.agent_resource}")


if __name__ == "__main__":
    main()
