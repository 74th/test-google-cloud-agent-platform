"""Thin Claude Agent SDK adapter with an explicit text-only contract."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


class AgentInvocationError(RuntimeError):
    """An error that callers can safely report without exposing credentials."""


WORKSPACE = Path(__file__).resolve().parents[1] / "workspace"
MODEL = "claude-haiku-4-5@20251001"


def validate_message(message: object) -> str:
    if not isinstance(message, str) or not message.strip():
        raise AgentInvocationError("input.message は空でない文字列で指定してください。")
    if len(message) > 4_000:
        raise AgentInvocationError("input.message は4000文字以下で指定してください。")
    return message.strip()


def _prompt(message: str, now: datetime | None = None) -> str:
    current = (now or datetime.now(ZoneInfo("Asia/Tokyo"))).astimezone(ZoneInfo("Asia/Tokyo"))
    return (
        "workspace/.claude/skills/bus-schedule/SKILL.md の「金沢テストバス時刻表」を必ず使い、"
        "質問へ日本語で簡潔に回答してください。外部の時刻表を参照せず、"
        f"現在時刻は日本標準時 {current:%Y-%m-%d %H:%M} です。\n\n利用者の質問: {message}"
    )


async def invoke(message: object) -> str:
    """Run one stateless Agent SDK query and return its final text only."""
    text = validate_message(message)
    try:
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

        options = ClaudeAgentOptions(cwd=str(WORKSPACE), model=MODEL)
        async for event in query(prompt=_prompt(text), options=options):
            if isinstance(event, ResultMessage):
                result = getattr(event, "result", None)
                if isinstance(result, str) and result.strip():
                    return result.strip()
                raise AgentInvocationError("Claude Agent SDK が空の最終応答を返しました。")
    except AgentInvocationError:
        raise
    except Exception as exc:
        raise AgentInvocationError(
            "Claude Agent SDK の呼び出しに失敗しました。認証情報とランタイム設定を確認してください。"
        ) from exc
    raise AgentInvocationError("Claude Agent SDK から最終応答を取得できませんでした。")


async def stream_invoke(message: object) -> AsyncIterator[dict[str, str]]:
    """Expose the normalized answer as an NDJSON-compatible stream chunk."""
    yield {"output": await invoke(message)}
