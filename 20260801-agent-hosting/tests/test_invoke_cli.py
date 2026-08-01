import json

import pytest

from scripts import invoke_agent


def test_endpoint_requires_full_resource_name() -> None:
    with pytest.raises(ValueError):
        invoke_agent.endpoint("agent-1", "asia-northeast1")


def test_endpoint_uses_reasoning_engine_query_method() -> None:
    assert (
        invoke_agent.endpoint("projects/1/locations/us-central1/reasoningEngines/a", "us-central1")
        == "https://us-central1-aiplatform.googleapis.com/v1/projects/1/locations/us-central1/reasoningEngines/a:query"
    )


def test_invoke_rejects_invalid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(invoke_agent, "token", lambda: "test-token")

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps({"unexpected": "value"}).encode()

    monkeypatch.setattr(invoke_agent.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(RuntimeError, match="有効なテキスト応答"):
        invoke_agent.invoke("projects/1/locations/asia-northeast1/reasoningEngines/a", "asia-northeast1", "hi")


def test_invoke_reports_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(invoke_agent, "token", lambda: "test-token")
    monkeypatch.setattr(
        invoke_agent.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(invoke_agent.urllib.error.URLError("offline")),
    )
    with pytest.raises(RuntimeError, match="接続できません"):
        invoke_agent.invoke("projects/1/locations/asia-northeast1/reasoningEngines/a", "asia-northeast1", "hi")
