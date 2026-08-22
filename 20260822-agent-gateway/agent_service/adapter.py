"""Claude Agent SDK adapter with an explicit web-retrieval contract."""

from __future__ import annotations

import asyncio
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse
from collections.abc import AsyncIterator
from datetime import datetime
from types import SimpleNamespace
from typing import Any

MODEL = "claude-haiku-4-5@20251001"
MAX_MESSAGE_LENGTH = 4_000
FETCH_TOOL_NAME = "GatewayWebFetch"
# This is an in-process SDK MCP tool named WebFetch. The built-in Claude Code
# WebFetch calls claude.ai for a preflight decision, which would move the
# destination decision outside Agent Gateway. The local tool performs the
# requested URL fetch in this container, so the Runtime proxy exposes the real
# destination (for example, github.com) to Agent Gateway.
ALLOWED_TOOLS = [f"mcp__web__{FETCH_TOOL_NAME}"]
MAX_FETCH_BYTES = 120_000


class AgentInvocationError(RuntimeError):
    """An error safe to return to a caller without disclosing credentials."""


def _exception_types(error: BaseException) -> str:
    """Return only exception type names, including nested exception groups."""
    types = [type(error).__name__]
    if isinstance(error, BaseExceptionGroup):
        for child in error.exceptions:
            types.append(_exception_types(child))
    return "/".join(types)


def _sdk_stderr(line: str) -> None:
    """Forward SDK diagnostics while masking credential-shaped values."""
    safe = re.sub(r"(?i)(authorization|bearer|token|api[-_]?key)[^\s]*", "\\1=[redacted]", line)
    print(f"Claude SDK: {safe[:1000]}", file=sys.stderr, flush=True)


def validate_message(message: object) -> str:
    if not isinstance(message, str) or not message.strip():
        raise AgentInvocationError("input.message は空でない文字列で指定してください。")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise AgentInvocationError("input.message は4000文字以下で指定してください。")
    return message.strip()


def system_prompt() -> str:
    return (
        "あなたは外部ページの内容を確認する検証エージェントです。"
        f"利用者が URL を指定した場合は、必ず {FETCH_TOOL_NAME} でその URL を実際に取得してから回答してください。"
        "取得が拒否、失敗、空結果、または不完全だった場合は、その事実を日本語で明示してください。"
        "取得できなかったページの内容や数値を事前知識・推測・記憶で補完してはいけません。"
        "取得できた内容だけを根拠に、簡潔な日本語で回答してください。"
    )


def build_prompt(message: str) -> str:
    return f"{system_prompt()}\n\n利用者の指示:\n{message}"


def sdk_options(cwd: str | None = None) -> dict[str, Any]:
    """Return the pinned SDK options as a plain mapping for easy inspection."""
    options: dict[str, Any] = {
        "model": MODEL,
        "permission_mode": "bypassPermissions",
        "allowed_tools": ALLOWED_TOOLS.copy(),
        "env": {
            "CLAUDE_CODE_USE_VERTEX": "1",
            "ANTHROPIC_VERTEX_PROJECT_ID": "nnyn-dev",
            "CLOUD_ML_REGION": "global",
            "ANTHROPIC_MODEL": MODEL,
        },
    }
    if cwd:
        options["cwd"] = cwd
    return options


def _fetch_url(url: object) -> str:
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        return "WebFetch failed: url must use http:// or https://."
    host = urlparse(url).hostname or "unknown"
    print(f"GatewayWebFetch request host={host}", file=sys.stderr, flush=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "20260822-agent-gateway-webfetch/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(MAX_FETCH_BYTES + 1)
            if len(data) > MAX_FETCH_BYTES:
                data = data[:MAX_FETCH_BYTES]
            charset = response.headers.get_content_charset() or "utf-8"
            final_host = urlparse(response.geturl()).hostname or "unknown"
            print(
                f"GatewayWebFetch response host={host} final_host={final_host} "
                f"status={response.status} bytes={len(data)}",
                file=sys.stderr,
                flush=True,
            )
            return data.decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        print(
            f"GatewayWebFetch response host={host} status={exc.code}",
            file=sys.stderr,
            flush=True,
        )
        return f"WebFetch failed: the requested page could not be retrieved ({type(exc).__name__})."
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(
            f"GatewayWebFetch error host={host} type={type(exc).__name__}",
            file=sys.stderr,
            flush=True,
        )
        return f"WebFetch failed: the requested page could not be retrieved ({type(exc).__name__})."


def web_fetch_server() -> object:
    """Build the local SDK MCP server that exposes only WebFetch."""
    # claude-agent-sdk 0.1.9 routes SDK MCP requests through the server's
    # request_handlers. Its helper targets an older MCP Server API, while the
    # pinned Python 3.12 lock resolves mcp 2.x, so keep this bridge explicit.
    from mcp.types import CallToolRequest, CallToolResult, ListToolsRequest, TextContent

    async def list_tools(_: object) -> object:
        return SimpleNamespace(
            # claude-agent-sdk 0.1.9 only reads root.tools and expects the
            # pre-mcp-2.0 camelCase inputSchema attribute. Avoid constructing
            # mcp 2.0.0's Pydantic ListToolsResult, which validates the
            # descriptor against its newer input_schema model.
            root=SimpleNamespace(
                tools=[
                    SimpleNamespace(
                        name=FETCH_TOOL_NAME,
                        description="Fetch a specified HTTP(S) URL and return its current page content.",
                        inputSchema={
                            "type": "object",
                            "properties": {"url": {"type": "string"}},
                            "required": ["url"],
                        },
                    )
                ]
            )
        )

    async def call_tool(request: CallToolRequest) -> object:
        if request.params.name != FETCH_TOOL_NAME:
            return SimpleNamespace(
                root=CallToolResult(
                    content=[TextContent(text=f"WebFetch failed: unknown tool {request.params.name}.")],
                    isError=True,
                )
            )
        args = request.params.arguments or {}
        content = await asyncio.to_thread(_fetch_url, args.get("url"))
        return SimpleNamespace(root=CallToolResult(content=[TextContent(text=content)]))

    return SimpleNamespace(
        name="web",
        version="1.0.0",
        request_handlers={
            ListToolsRequest: list_tools,
            CallToolRequest: call_tool,
        }
    )


async def _prompt_stream(
    prompt: str, finished: asyncio.Event | None = None
) -> AsyncIterator[dict[str, Any]]:
    """Send one prompt while keeping stdin open for SDK-MCP callbacks.

    claude-agent-sdk 0.1.9 closes the subprocess stdin as soon as a finite
    async prompt stream ends. SDK-MCP requests can arrive after that point,
    so keep the stream alive until the final result has been observed.
    """
    yield {
        "type": "user",
        "message": {"role": "user", "content": prompt},
        "parent_tool_use_id": None,
        "session_id": "",
    }
    if finished is not None:
        await finished.wait()


async def invoke(message: object) -> str:
    """Run one stateless Agent SDK query and return only its final text."""
    text = validate_message(message)
    try:
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

        options = ClaudeAgentOptions(
            **sdk_options(),
            stderr=_sdk_stderr,
            mcp_servers={
                "web": {
                    "type": "sdk",
                    "name": "web",
                    "instance": web_fetch_server(),
                }
            },
        )
        final_result: str | None = None
        finished = asyncio.Event()
        async for event in query(
            prompt=_prompt_stream(build_prompt(text), finished), options=options
        ):
            if isinstance(event, ResultMessage):
                result = getattr(event, "result", None)
                if isinstance(result, str) and result.strip():
                    final_result = result.strip()
                    finished.set()
                else:
                    raise AgentInvocationError("Claude Agent SDK が空の最終応答を返しました。")
        if final_result:
            return final_result
        raise AgentInvocationError("Claude Agent SDK から最終応答を取得できませんでした。")
    except AgentInvocationError:
        raise
    except Exception as exc:
        raise AgentInvocationError(
            "Claude Agent SDK の呼び出しに失敗しました。認証情報とランタイム設定を確認してください。"
            f"（内部分類: {_exception_types(exc)}）"
        ) from exc
    raise AgentInvocationError("Claude Agent SDK から最終応答を取得できませんでした。")


async def stream_invoke(message: object) -> AsyncIterator[dict[str, str]]:
    """Expose the normalized answer as an NDJSON-compatible stream chunk."""
    yield {"output": await invoke(message)}
