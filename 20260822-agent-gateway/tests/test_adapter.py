import asyncio
import sys
import types
import urllib.error

import pytest

from agent_service import adapter


@pytest.mark.parametrize("message", [None, "", "  ", 42])
def test_rejects_invalid_messages(message: object) -> None:
    with pytest.raises(adapter.AgentInvocationError, match="input.message"):
        adapter.validate_message(message)


def test_prompt_requires_real_fetch_and_forbids_memory_completion() -> None:
    prompt = adapter.build_prompt("https://github.com/74th の内容を要約して")
    assert "WebFetch" in prompt
    assert "実際に取得" in prompt
    assert "事前知識" in prompt


def test_sdk_options_pin_model_vertex_and_minimal_tool() -> None:
    options = adapter.sdk_options()
    assert options["model"] == "claude-haiku-4-5@20251001"
    assert options["allowed_tools"] == [f"mcp__web__{adapter.FETCH_TOOL_NAME}"]
    assert options["permission_mode"] == "bypassPermissions"
    assert options["env"]["CLAUDE_CODE_USE_VERTEX"] == "1"
    assert options["env"]["CLOUD_ML_REGION"] == "global"
    assert "ANTHROPIC_API_KEY" not in options["env"]


def test_invoke_returns_final_result(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeOptions:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    class FakeResultMessage:
        result = "GitHub の回答"

    async def fake_query(**kwargs: object):
        captured["prompt"] = kwargs["prompt"]
        yield FakeResultMessage()

    def fake_tool(name: str, description: str, schema: dict[str, type]):
        def decorate(handler):
            return handler

        return decorate

    def fake_server(name: str, tools: list[object]):
        return {"name": name, "tools": tools}

    monkeypatch.setitem(
        sys.modules,
        "claude_agent_sdk",
        types.SimpleNamespace(
            ClaudeAgentOptions=FakeOptions,
            ResultMessage=FakeResultMessage,
            query=fake_query,
            tool=fake_tool,
            create_sdk_mcp_server=fake_server,
        ),
    )
    assert asyncio.run(adapter.invoke("hi")) == "GitHub の回答"
    assert captured["model"] == adapter.MODEL


def test_sdk_exception_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeOptions:
        def __init__(self, **_: object) -> None:
            pass

    async def fake_query(**_: object):
        raise RuntimeError("secret token must not leak")
        yield  # pragma: no cover

    monkeypatch.setitem(
        sys.modules,
        "claude_agent_sdk",
        types.SimpleNamespace(ClaudeAgentOptions=FakeOptions, ResultMessage=object, query=fake_query),
    )
    with pytest.raises(adapter.AgentInvocationError, match="認証情報") as exc:
        asyncio.run(adapter.invoke("hi"))
    assert "secret token" not in str(exc.value)


def test_web_fetch_rejects_non_http_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def urlopen(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("urlopen should not be called")

    monkeypatch.setattr(adapter.urllib.request, "urlopen", urlopen)
    assert "url must use" in adapter._fetch_url("ftp://example.test/page")
    assert called is False


def test_web_fetch_returns_content_and_applies_size_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    class Headers:
        def get_content_charset(self):
            return "utf-8"

    class Response:
        status = 200
        headers = Headers()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def geturl(self):
            return "https://example.test/final"

        def read(self, size):
            assert size == adapter.MAX_FETCH_BYTES + 1
            return ("x" * (size + 20)).encode()

    monkeypatch.setattr(adapter.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    result = adapter._fetch_url("https://example.test/page")
    assert len(result) == adapter.MAX_FETCH_BYTES


def test_web_fetch_reports_http_403(monkeypatch: pytest.MonkeyPatch) -> None:
    error = urllib.error.HTTPError(
        "https://example.test/page", 403, "Forbidden", {}, None
    )
    monkeypatch.setattr(adapter.urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(error))
    result = adapter._fetch_url("https://example.test/page")
    assert "could not be retrieved" in result
