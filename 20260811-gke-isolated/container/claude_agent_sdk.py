#!/usr/bin/env python3
"""Run one Claude Agent SDK request through Vertex AI."""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from urllib.request import Request, urlopen

# The executable intentionally has the same name as the SDK package because
# the acceptance command is `python claude_agent_sdk.py`. Remove /app while
# importing so Python resolves the installed package instead of this file.
SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIRECTORY in sys.path:
    sys.path.remove(SCRIPT_DIRECTORY)

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

sys.path.insert(0, SCRIPT_DIRECTORY)


MODEL = "claude-haiku-4-5@20251001"
URL_PATTERN = re.compile(r"https?://[^\s]+")
MAX_FETCH_BYTES = 50000


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

    prompt_with_context = prompt
    url_match = URL_PATTERN.search(prompt)
    if url_match:
        url = url_match.group(0).rstrip("。、，,.)】")
        request = Request(url, headers={"User-Agent": "gke-isolated-claude-agent/1.0"})
        with urlopen(request, timeout=20) as response:  # noqa: S310 - URL is user input by design
            content = response.read(MAX_FETCH_BYTES + 1)
            charset = response.headers.get_content_charset() or "utf-8"
        if len(content) > MAX_FETCH_BYTES:
            content = content[:MAX_FETCH_BYTES]
        fetched_text = content.decode(charset, errors="replace")
        prompt_with_context = (
            f"{prompt}\n\nFetched content from {url}:\n"
            f"--- BEGIN FETCHED CONTENT ---\n{fetched_text}\n"
            "--- END FETCHED CONTENT ---\n"
            "Use the fetched content to answer the user's request."
        )

    options = ClaudeAgentOptions(
        model=MODEL,
        allowed_tools=[],
        max_turns=3,
        permission_mode="bypassPermissions",
    )
    final_result: str | None = None
    async for message in query(prompt=prompt_with_context, options=options):
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
