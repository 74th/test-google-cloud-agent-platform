from __future__ import annotations

import json

import pytest

from claude_session_store.claude import ClaudeError
from claude_session_store.config import ConfigurationError, Settings, VERTEX_HAIKU_4_5_MODEL
from claude_session_store.service import resume, start
from claude_session_store.session_store import GoogleSessionStore, IncompleteSessionError, SessionNotFoundError


class FakeSessions:
    def __init__(self, state): self.state = state
    def create(self, *, name, user_id, config=None):
        self.state["name"] = f"{name}/sessions/session-1"
        return {"name": self.state["name"]}
    def get(self, *, name):
        if name != self.state.get("name"): raise RuntimeError("404 not found")
        return {"name": name}


class FakeEvents:
    def __init__(self, state, fail=False): self.state, self.fail = state, fail
    def append(self, **kwargs):
        if self.fail: raise RuntimeError("append denied")
        self.state.setdefault("events", []).append({"content": kwargs["config"]["content"], **kwargs})
    def list(self, *, name): return self.state.get("events", [])


class FakeClaude:
    def __init__(self, missing_transcript=False): self.missing_transcript, self.last_resume = missing_transcript, None
    async def run(self, prompt, resume=None):
        self.last_resume = resume
        if resume and self.missing_transcript: raise ClaudeError("ローカルトランスクリプトがありません")
        if resume: return resume, "nonce-123"
        return "claude-1", "nonce-123"


def settings(tmp_path):
    return Settings("project", "us-central1", "projects/project/locations/us-central1/reasoningEngines/engine", "user", tmp_path, "us-east5")


def store(settings, state, fail=False):
    return GoogleSessionStore(settings, FakeSessions(state), FakeEvents(state, fail))


def test_start_saves_ordered_events_and_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr("claude_session_store.service.secrets.token_urlsafe", lambda _: "nonce-123")
    state = {}
    result = start(store(settings(tmp_path), state), FakeClaude())
    assert result.session_created and result.events_appended
    assert [event["content"]["role"] for event in state["events"]] == ["user", "assistant", "system"]
    assert json.loads(state["events"][2]["content"]["parts"][0]["text"])["claude_session_id"] == "claude-1"


def test_tool_interaction_is_saved_as_portable_trace_events(tmp_path):
    state = {"name": "session"}
    target = store(settings(tmp_path), state)
    target.append_tool_interaction("session", "ask_human", {"question": "continue?"}, "approved")
    traces = [json.loads(event["content"]["parts"][0]["text"]) for event in state["events"]]
    assert traces == [
        {"event_type": "tool_call", "input": {"question": "continue?"}, "schema_version": "1", "tool_name": "ask_human"},
        {"event_type": "tool_result", "result": "approved", "schema_version": "1", "tool_name": "ask_human"},
    ]


def test_two_independent_stages_reach_nonce_match(tmp_path, monkeypatch):
    monkeypatch.setattr("claude_session_store.service.secrets.token_urlsafe", lambda _: "nonce-123")
    state = {}
    first_process = start(store(settings(tmp_path), state), FakeClaude())
    second_process = resume(store(settings(tmp_path), state), FakeClaude(), first_process.session_name)
    assert second_process.success


@pytest.mark.parametrize("events,error", [([], IncompleteSessionError)])
def test_incomplete_events_are_rejected(tmp_path, events, error):
    state = {"name": "session", "events": events}
    with pytest.raises(error): store(settings(tmp_path), state).retrieve_conversation("session")


def test_missing_session_is_not_created(tmp_path):
    with pytest.raises(SessionNotFoundError): store(settings(tmp_path), {}).retrieve_conversation("missing")


def test_append_failure_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr("claude_session_store.service.secrets.token_urlsafe", lambda _: "nonce-123")
    result = start(store(settings(tmp_path), {}, fail=True), FakeClaude())
    assert not result.events_appended and result.error_stage == "events_appended" and not result.success


def test_missing_local_transcript_keeps_retrieval_success(tmp_path, monkeypatch):
    monkeypatch.setattr("claude_session_store.service.secrets.token_urlsafe", lambda _: "nonce-123")
    state = {}
    initial = start(store(settings(tmp_path), state), FakeClaude())
    result = resume(store(settings(tmp_path), state), FakeClaude(missing_transcript=True), initial.session_name)
    assert result.events_retrieved and not result.claude_resumed and result.error_stage == "claude_resumed"


def test_required_environment_variables_are_reported(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for name in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GOOGLE_CLOUD_AGENT_ENGINE", "SESSION_STORE_USER_ID", "CLAUDE_SESSION_CWD", "VERTEX_AI_LOCATION"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigurationError, match="GOOGLE_CLOUD_PROJECT"):
        Settings.from_env()


def test_vertex_ai_uses_the_fixed_haiku_4_5_model():
    assert VERTEX_HAIKU_4_5_MODEL == "claude-haiku-4-5@20251001"


def test_vertex_settings_do_not_require_an_anthropic_api_key(monkeypatch, tmp_path):
    values = {
        "GOOGLE_CLOUD_PROJECT": "nnyn-dev", "GOOGLE_CLOUD_LOCATION": "us-central1",
        "GOOGLE_CLOUD_AGENT_ENGINE": "projects/nnyn-dev/locations/us-central1/reasoningEngines/engine",
        "SESSION_STORE_USER_ID": "user", "CLAUDE_SESSION_CWD": str(tmp_path), "VERTEX_AI_LOCATION": "us-east5",
    }
    for name, value in values.items(): monkeypatch.setenv(name, value)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    configured = Settings.from_env()
    assert configured.project == "nnyn-dev" and configured.model == VERTEX_HAIKU_4_5_MODEL


def test_result_json_is_success_only_when_every_stage_passes(tmp_path):
    incomplete = resume(store(settings(tmp_path), {}), FakeClaude(), "missing")
    assert set(incomplete.to_dict()) >= {"success", "session_created", "events_appended", "events_retrieved", "claude_resumed", "nonce_matched", "error_stage"}
    assert not incomplete.to_dict()["success"]
