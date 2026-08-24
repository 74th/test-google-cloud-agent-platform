from __future__ import annotations

import asyncio
import sys
import types

import pytest

from agent_service.adapter import ClaudeAgentAdapter, remote_mcp_config
from agent_service.credentials import StaticTokenProvider
from agent_service.errors import Stage, ValidationError
from agent_service.models import RegistryEntry, TargetConfig
from agent_service.registry import RegistryResolver


TOOL = {
    "name": "validate_echo",
    "description": "Return a deterministic validation response for the 20260823-mcp-server experiment.",
    "inputSchema": {
        "type": "object",
        "properties": {"message": {"type": "string", "minLength": 1, "maxLength": 256}},
        "required": ["message"],
    },
}


def service(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "name": "projects/test/locations/us-central1/services/run-service",
        "endpointId": "urn:endpoint:test",
        "interfaces": [{"url": "https://run.example.test/mcp", "protocolBinding": "JSONRPC"}],
        "mcpServerSpec": {"tools": [TOOL]},
    }
    value.update(overrides)
    return value


class FakeRegistry:
    def __init__(self, current: dict[str, object]):
        self.current = current
        self.calls = 0

    def describe(self, project: str, location: str, service_id: str) -> dict[str, object]:
        self.calls += 1
        return self.current


def resolver(registry: FakeRegistry) -> RegistryResolver:
    return RegistryResolver(
        registry,
        "test",
        "us-central1",
        {"cloud-run": TargetConfig("cloud-run", "run-service", frozenset({"run.example.test"}), "https://run.example.test")},
        {"cloud-run": TOOL},
    )


def test_resolver_uses_fixed_service_and_rejects_url_before_network() -> None:
    registry = FakeRegistry(service())
    with pytest.raises(ValidationError, match="URLs") as error:
        resolver(registry).resolve("cloud-run", requested_url="https://attacker.example.test/mcp")
    assert error.value.stage is Stage.METADATA_VALIDATION
    assert registry.calls == 0


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value["name"].replace("run-service", "other-service"),
        lambda value: [{"url": "http://run.example.test/mcp", "protocolBinding": "JSONRPC"}],
        lambda value: [{"url": "https://attacker.example.test/mcp", "protocolBinding": "JSONRPC"}],
        lambda value: [{"url": "https://run.example.test/mcp", "protocolBinding": "HTTP_JSON"}],
        lambda value: {"tools": [{"name": "validate_echo", "description": "tampered", "inputSchema": TOOL["inputSchema"]}]},
    ],
)
def test_metadata_validation_fails_before_token_generation(mutator) -> None:
    value = service()
    if isinstance(mutator(value), str):
        value["name"] = mutator(value)
    else:
        value["interfaces"] = mutator(value)
    with pytest.raises(ValidationError) as error:
        resolver(FakeRegistry(value)).resolve("cloud-run")
    assert error.value.stage in {Stage.METADATA_VALIDATION, Stage.REGISTRY_DISCOVERY}


def test_lifecycle_is_resolved_per_invocation_and_deleted_entry_has_no_cache() -> None:
    registry = FakeRegistry(service())
    instance = resolver(registry)
    assert instance.resolve("cloud-run").url == "https://run.example.test/mcp"
    registry.current = service(interfaces=[{"url": "https://run.example.test/changed", "protocolBinding": "JSONRPC"}])
    assert instance.resolve("cloud-run").url.endswith("/changed")
    registry.current = {"name": "projects/test/locations/us-central1/services/run-service", "interfaces": []}
    with pytest.raises(ValidationError, match="metadata"):
        instance.resolve("cloud-run")
    assert registry.calls == 3


def test_token_is_short_lived_boundary_and_exact_audience_is_used() -> None:
    provider = StaticTokenProvider(lambda audience: f"token-for-{audience}")
    entry = RegistryEntry("cloud-run", "test", "us-central1", "run-service", "endpoint", "https://run.example.test/mcp", "run.example.test", "JSONRPC", TOOL, "https://run.example.test")
    config = remote_mcp_config(entry, provider.id_token(entry.audience), "mcp-correlation-1")
    assert provider.audiences == ["https://run.example.test"]
    assert config["headers"]["Authorization"] == "Bearer token-for-https://run.example.test"
    assert "token-for" not in str({"correlation_id": "mcp-correlation-1"})


def test_token_mint_denial_is_stage_specific_and_sanitized() -> None:
    provider = StaticTokenProvider(lambda _: (_ for _ in ()).throw(RuntimeError("secret-token-value")))
    with pytest.raises(ValidationError, match="generation failed") as error:
        provider.id_token("https://run.example.test")
    assert error.value.stage is Stage.TOKEN_GENERATION
    assert "secret-token-value" not in str(error.value)


def test_adapter_rejects_success_without_tool_event(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeOptions:
        def __init__(self, **kwargs: object):
            self.kwargs = kwargs

    class FakeResult:
        result = "モデルだけの回答"

    async def fake_query(**_: object):
        yield FakeResult()

    monkeypatch.setitem(sys.modules, "claude_agent_sdk", types.SimpleNamespace(ClaudeAgentOptions=FakeOptions, ResultMessage=FakeResult, query=fake_query))
    entry = RegistryEntry("cloud-run", "test", "us-central1", "run-service", "endpoint", "https://run.example.test/mcp", "run.example.test", "JSONRPC", TOOL, "https://run.example.test")
    adapter = ClaudeAgentAdapter(StaticTokenProvider(lambda _: "short-lived"))
    with pytest.raises(ValidationError) as error:
        asyncio.run(adapter.invoke(entry, "run the validation", types.SimpleNamespace(correlation_id="mcp-correlation-1", sdk_tool_events=[])))
    assert error.value.stage is Stage.TOOL_EXECUTION


def test_adapter_only_advertises_resolved_tool_and_not_user_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeOptions:
        def __init__(self, **kwargs: object):
            captured.update(kwargs)

    class ToolBlock:
        name = "validate_echo"

    class FakeAssistant:
        content = [ToolBlock()]

    class FakeResult:
        result = "実行結果"

    async def fake_query(**kwargs: object):
        yield FakeAssistant()
        yield FakeResult()

    monkeypatch.setitem(sys.modules, "claude_agent_sdk", types.SimpleNamespace(ClaudeAgentOptions=FakeOptions, ResultMessage=FakeResult, query=fake_query))
    entry = RegistryEntry("cloud-run", "test", "us-central1", "run-service", "endpoint", "https://run.example.test/mcp", "run.example.test", "JSONRPC", TOOL, "https://run.example.test")
    evidence = types.SimpleNamespace(correlation_id="mcp-correlation-1", sdk_tool_events=[])
    assert asyncio.run(ClaudeAgentAdapter(StaticTokenProvider(lambda _: "short-lived")).invoke(entry, "run the validation", evidence)) == "実行結果"
    options = captured["mcp_servers"]
    assert list(options) == ["cloud-run"]
    assert options["cloud-run"]["url"] == entry.url
    assert captured["allowed_tools"] == ["mcp__cloud-run__validate_echo"]
