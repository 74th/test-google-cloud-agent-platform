from __future__ import annotations

import json
import re
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from .credentials import TokenProvider
from .errors import Stage, ValidationError
from .models import InvocationEvidence, RegistryEntry

MODEL = "claude-haiku-4-5@20251001"
CORRELATION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{7,63}$")
URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)


def new_correlation_id() -> str:
    return f"mcp-{uuid.uuid4().hex[:24]}"


def validate_correlation_id(value: str) -> str:
    if not CORRELATION_PATTERN.fullmatch(value):
        raise ValueError("invalid correlation id")
    return value


def remote_mcp_config(entry: RegistryEntry, token: str, correlation_id: str) -> dict[str, Any]:
    """Build a per-invocation SDK config; token values never enter evidence."""
    return {
        "type": "http",
        "url": entry.url,
        "headers": {
            "Authorization": f"Bearer {token}",
            "X-MCP-Correlation-ID": correlation_id,
            "X-MCP-Hosting-Target": entry.target,
        },
    }


def objective_prompt(target: str, tool_name: str, correlation_id: str, message: str) -> str:
    return (
        "この検証では、指定された remote MCP Tool を必ず一度実行してから回答してください。"
        f" target={target}; tool={tool_name}; correlation={correlation_id}. "
        "Tool を実行できない場合は成功したと回答せず、失敗段階を返してください。\n"
        f"検証目的: {message}"
    )


def _tool_events(event: Any) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    content = getattr(event, "content", None)
    if not isinstance(content, list):
        return events
    for block in content:
        name = getattr(block, "name", None)
        if isinstance(name, str) and name:
            events.append({"name": name, "kind": type(block).__name__})
    return events


class ClaudeAgentAdapter:
    def __init__(
        self,
        token_provider: TokenProvider,
        query_fn: Callable[..., AsyncIterator[Any]] | None = None,
        model: str = MODEL,
    ):
        self.token_provider = token_provider
        self.query_fn = query_fn
        self.model = model

    async def invoke(
        self,
        entry: RegistryEntry,
        message: str,
        evidence: InvocationEvidence,
    ) -> str:
        if URL_PATTERN.search(message):
            raise ValidationError(Stage.METADATA_VALIDATION, "arbitrary endpoint URL is not accepted")
        try:
            token = self.token_provider.id_token(self._audience(entry))
        except ValidationError:
            raise
        except Exception as error:
            raise ValidationError(Stage.TOKEN_GENERATION, "ID token generation failed") from error
        config = remote_mcp_config(entry, token, evidence.correlation_id)
        try:
            from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

            query_fn = self.query_fn or query
            options = ClaudeAgentOptions(
                model=self.model,
                permission_mode="bypassPermissions",
                allowed_tools=[f"mcp__{entry.target}__{entry.tool['name']}"],
                mcp_servers={entry.target: config},
                env={
                    "CLAUDE_CODE_USE_VERTEX": "1",
                    "ANTHROPIC_VERTEX_PROJECT_ID": entry.project,
                    "CLOUD_ML_REGION": "global",
                    "ANTHROPIC_MODEL": self.model,
                    "VERTEX_REGION_CLAUDE_HAIKU_4_5": "global",
                },
            )
            final: str | None = None
            prompt = objective_prompt(entry.target, entry.tool["name"], evidence.correlation_id, message)
            async for event in query_fn(prompt=prompt, options=options):
                evidence.sdk_tool_events.extend(_tool_events(event))
                if isinstance(event, ResultMessage):
                    result = getattr(event, "result", None)
                    if isinstance(result, str) and result.strip():
                        final = result.strip()
            if not evidence.sdk_tool_events:
                raise ValidationError(Stage.TOOL_EXECUTION, "Claude returned without a remote Tool execution event")
            if not final:
                raise ValidationError(Stage.MCP_PROTOCOL, "Claude Agent SDK returned no final response")
            evidence.final_response = final
            return final
        except ValidationError:
            raise
        except Exception as error:
            raise ValidationError(Stage.MCP_PROTOCOL, f"Claude Agent SDK invocation failed ({type(error).__name__})") from error

    @staticmethod
    def _audience(entry: RegistryEntry) -> str:
        if not entry.audience:
            raise ValidationError(Stage.TOKEN_GENERATION, "reviewed authentication audience is missing")
        return entry.audience
