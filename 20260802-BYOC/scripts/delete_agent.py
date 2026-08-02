"""Delete only the explicitly named verification agent."""
from __future__ import annotations
import argparse
from pathlib import Path

def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project", required=True); parser.add_argument("--location", required=True); parser.add_argument("--agent-resource", required=True)
    args = parser.parse_args()
    if "/reasoningEngines/" not in args.agent_resource: parser.error("--agent-resource は完全な reasoningEngines リソース名で指定してください。")
    import vertexai
    vertexai.Client(project=args.project, location=args.location).agent_engines.delete(name=args.agent_resource)
    print(f"deleted: {args.agent_resource}")
if __name__ == "__main__": main()
