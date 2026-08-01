import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient

from agent_service.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_rejects_wrong_runtime_method(client: TestClient) -> None:
    response = client.post("/api/reasoning_engine", json={"class_method": "other", "input": {"message": "hi"}})
    assert response.status_code == 400


def test_rejects_empty_message_before_sdk(client: TestClient) -> None:
    response = client.post("/api/reasoning_engine", json={"class_method": "query", "input": {"message": ""}})
    assert response.status_code == 422
    assert "input.message" in response.json()["detail"]


def test_normalizes_sdk_text(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_invoke(message: object) -> str:
        assert message == "次のバスは何時？"
        return "8:35発、9:00着です。金沢テスト病院経由で約25分かかります。"

    monkeypatch.setattr("agent_service.app.invoke", fake_invoke)
    response = client.post("/api/reasoning_engine", json={"class_method": "query", "input": {"message": "次のバスは何時？"}})
    assert response.json() == {"output": "8:35発、9:00着です。金沢テスト病院経由で約25分かかります。"}


def test_accepts_agent_platform_json_string_body(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_invoke(message: object) -> str:
        assert message == "次のバスは何時？"
        return "8:35発、9:00着です。"

    monkeypatch.setattr("agent_service.app.invoke", fake_invoke)
    response = client.post(
        "/api/reasoning_engine",
        json=json.dumps({"class_method": "query", "input": {"message": "次のバスは何時？"}}),
    )
    assert response.json() == {"output": "8:35発、9:00着です。"}


def test_container_does_not_run_as_root() -> None:
    dockerfile = Path("Dockerfile").read_text()
    assert "USER agent" in dockerfile


@pytest.mark.parametrize(
    ("answer", "required", "forbidden"),
    [
        ("9:10発、9:22着です。", "9:22着", "金沢テスト病院"),
        ("掲載された時刻表には以降の便はありません。", "以降の便はありません", "発、"),
    ],
)
def test_timetable_responses_remain_displayable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, answer: str, required: str, forbidden: str
) -> None:
    async def fake_invoke(message: object) -> str:
        return answer

    monkeypatch.setattr("agent_service.app.invoke", fake_invoke)
    response = client.post("/api/reasoning_engine", json={"class_method": "query", "input": {"message": "次のバスは何時？"}})
    assert required in response.json()["output"]
    assert forbidden not in response.json()["output"]
