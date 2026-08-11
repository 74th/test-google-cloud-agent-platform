#!/usr/bin/env python3
"""Run one Claude Agent SDK request through Vertex AI."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query


MODEL = "claude-haiku-4-5@20251001"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="One-shot prompt sent to Claude")
    return parser.parse_args()


async def run(prompt: str) -> str:
    project_id = os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT"
    )
    if not project_id:
        raise RuntimeError(
            "ANTHROPIC_VERTEX_PROJECT_ID or GOOGLE_CLOUD_PROJECT must be set"
        )

    os.environ["CLAUDE_CODE_USE_VERTEX"] = "1"
    os.environ.setdefault("CLOUD_ML_REGION", "global")
    os.environ["ANTHROPIC_VERTEX_PROJECT_ID"] = project_id

    options = ClaudeAgentOptions(
        model=MODEL,
        allowed_tools=["WebFetch"],
        max_turns=3,
        permission_mode="bypassPermissions",
    )
    final_result: str | None = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            final_result = message.result

    if not final_result:
        raise RuntimeError("Claude Agent SDK returned no final response")
    return final_result


def main() -> int:
    args = parse_args()
    try:
        print(asyncio.run(run(args.prompt)))
    except Exception as error:  # noqa: BLE001 - preserve a useful CLI error
        print(f"claude_agent_sdk.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
