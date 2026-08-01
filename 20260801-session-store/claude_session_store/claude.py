from __future__ import annotations

import os
from typing import Any, Protocol

from .config import Settings


class ClaudeError(RuntimeError):
    pass


class ClaudeRunner(Protocol):
    async def run(self, prompt: str, resume: str | None = None, *,
                  mcp_servers: dict[str, Any] | None = None,
                  allowed_tools: list[str] | None = None,
                  max_turns: int = 1) -> tuple[str, str]: ...


class AgentSdkRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def run(self, prompt: str, resume: str | None = None, *,
                  mcp_servers: dict[str, Any] | None = None,
                  allowed_tools: list[str] | None = None,
                  max_turns: int = 1) -> tuple[str, str]:
        try:
            from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage, query
        except ImportError as error:
            raise ClaudeError("claude-agent-sdk をインストールしてください") from error
        vertex_env = dict(os.environ)
        vertex_env.update({
            "CLAUDE_CODE_USE_VERTEX": "1",
            "ANTHROPIC_VERTEX_PROJECT_ID": self.settings.project,
            "CLOUD_ML_REGION": self.settings.vertex_location,
        })
        options: dict[str, Any] = {
            "cwd": str(self.settings.claude_cwd), "max_turns": max_turns,
            "allowed_tools": allowed_tools or [],
            "model": self.settings.model, "env": vertex_env,
        }
        if mcp_servers:
            options["mcp_servers"] = mcp_servers
        if resume:
            options["resume"] = resume
        result = None
        try:
            agent_options = ClaudeAgentOptions(**options)
            if mcp_servers:
                # in-process MCP ツールは ClaudeSDKClient 経由で制御要求を処理する。
                async with ClaudeSDKClient(options=agent_options) as client:
                    await client.query(prompt)
                    async for message in client.receive_response():
                        if isinstance(message, ResultMessage):
                            result = message
            else:
                async for message in query(prompt=prompt, options=agent_options):
                    if isinstance(message, ResultMessage):
                        result = message
        except Exception as error:
            raise ClaudeError(f"Claude Agent SDK の実行または再開に失敗しました: {error}") from error
        if result is None or not result.session_id or result.result is None:
            raise ClaudeError("Claude Agent SDK から ResultMessage または session_id を取得できませんでした")
        return result.session_id, result.result
