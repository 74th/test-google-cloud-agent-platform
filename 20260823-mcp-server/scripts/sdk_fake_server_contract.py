#!/usr/bin/env python3
"""Exercise pinned Claude Agent SDK remote MCP discovery and Tool execution.

The fake server is local and accepts only the expected refreshed bearer value.
Vertex AI is used only to make Claude choose the advertised fake Tool; no
credential or response is written to disk.
"""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from claude_agent_sdk import ClaudeAgentOptions, query


class FakeMCPHandler(BaseHTTPRequestHandler):
    calls: list[tuple[str, str]] = []
    expected_token = ""

    def log_message(self, *_: object) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", "0"))))
        auth = self.headers.get("authorization", "")
        self.calls.append((body.get("method", ""), auth))
        if auth != f"Bearer {self.expected_token}":
            self.send_response(401)
            self.end_headers()
            return
        method = body.get("method")
        if method == "initialize":
            result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": {"name": "local-contract", "version": "1"}}
        elif method == "notifications/initialized":
            self.send_response(202)
            self.end_headers()
            return
        elif method == "tools/list":
            result = {"tools": [{"name": "validate_echo", "description": "Return a deterministic fake result.", "inputSchema": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}}]}
        elif method == "tools/call":
            result = {"content": [{"type": "text", "text": "local fake Tool executed"}], "isError": False}
        else:
            result = {}
        payload = json.dumps({"jsonrpc": "2.0", "id": body.get("id"), "result": result}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


async def run_once(url: str, token: str) -> None:
    FakeMCPHandler.expected_token = token
    options = ClaudeAgentOptions(
        mcp_servers={"remote": {"type": "http", "url": url, "headers": {"Authorization": f"Bearer {token}"}}},
        allowed_tools=["mcp__remote__validate_echo"],
        model="claude-haiku-4-5@20251001",
        max_turns=2,
        permission_mode="bypassPermissions",
        env={
            "CLAUDE_CODE_USE_VERTEX": "1",
            "ANTHROPIC_VERTEX_PROJECT_ID": "nnyn-dev",
            "CLOUD_ML_REGION": "global",
            "ANTHROPIC_MODEL": "claude-haiku-4-5@20251001",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-4-5@20251001",
            "VERTEX_REGION_CLAUDE_HAIKU_4_5": "global",
        },
    )
    async for _ in query(prompt="必ず remote の validate_echo を呼び出し、Tool結果だけを根拠に回答してください。", options=options):
        pass


async def main() -> None:
    FakeMCPHandler.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeMCPHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/mcp"
    try:
        await run_once(url, "refreshed-local-contract-1")
        first = list(FakeMCPHandler.calls)
        FakeMCPHandler.calls = []
        await run_once(url, "refreshed-local-contract-2")
        second = list(FakeMCPHandler.calls)
    finally:
        server.shutdown()
    for calls, token in ((first, "refreshed-local-contract-1"), (second, "refreshed-local-contract-2")):
        methods = [method for method, _ in calls]
        assert "initialize" in methods and "tools/list" in methods and "tools/call" in methods, calls
        assert calls and all(auth == f"Bearer {token}" for _, auth in calls), calls
    print("Claude Agent SDK remote MCP contract passed: initialize, tools/list, tools/call, refreshed headers.")


if __name__ == "__main__":
    asyncio.run(main())
