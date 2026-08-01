from datetime import datetime
import asyncio
import sys
import types
from zoneinfo import ZoneInfo

import pytest

from agent_service import adapter


def test_skill_is_packaged_source_of_truth() -> None:
    skill = adapter.WORKSPACE / ".claude/skills/bus-schedule/SKILL.md"
    assert skill.is_file()
    assert "金沢テストバス時刻表" in skill.read_text()


@pytest.mark.parametrize("message", [None, "", "  ", 42])
def test_rejects_invalid_messages(message: object) -> None:
    with pytest.raises(adapter.AgentInvocationError, match="input.message"):
        adapter.validate_message(message)


def test_prompt_uses_jst_and_skill() -> None:
    now = datetime(2026, 8, 1, 8, 30, tzinfo=ZoneInfo("Asia/Tokyo"))
    prompt = adapter._prompt("次のバスは何時？", now)
    assert "金沢テストバス時刻表" in prompt
    assert ".claude/skills/bus-schedule/SKILL.md" in prompt
    assert "workspace/.claude" not in prompt
    assert "2026-08-01 08:30" in prompt


def test_sdk_options_pin_haiku_4_5(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeOptions:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    class FakeResultMessage:
        result = "回答"

    async def fake_query(**_: object):
        yield FakeResultMessage()

    fake_sdk = types.SimpleNamespace(
        ClaudeAgentOptions=FakeOptions,
        ResultMessage=FakeResultMessage,
        query=fake_query,
    )
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_sdk)
    assert asyncio.run(adapter.invoke("次のバスは何時？")) == "回答"
    assert captured["model"] == "claude-haiku-4-5@20251001"
    assert captured["permission_mode"] == "bypassPermissions"
