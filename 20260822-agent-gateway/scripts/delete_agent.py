"""Delete only the explicitly supplied Agent Runtime resource."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--agent-resource", required=True)
    args = parser.parse_args()
    if not args.agent_resource.startswith("projects/"):
        parser.error("--agent-resource は完全な projects/... リソース名で指定してください。")
    try:
        import vertexai

        vertexai.Client(project=args.project, location=args.location).agent_engines.delete(
            name=args.agent_resource
        )
        print(f"deleted {args.agent_resource}")
    except Exception as exc:
        raise SystemExit(f"エージェントの削除に失敗しました: {exc}") from exc


if __name__ == "__main__":
    main()
