from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Any, Iterable, Protocol

from .config import Settings
from .models import SAMPLE_VERSION, SCHEMA_VERSION, StoredConversation


class SessionStoreError(RuntimeError):
    pass


class SessionNotFoundError(SessionStoreError):
    pass


class IncompleteSessionError(SessionStoreError):
    pass


class SessionApi(Protocol):
    def create(self, *, name: str, user_id: str) -> Any: ...
    def get(self, *, name: str) -> Any: ...
    def delete(self, *, name: str) -> Any: ...


class EventsApi(Protocol):
    def append(self, **kwargs: Any) -> Any: ...
    def list(self, *, name: str) -> Iterable[Any]: ...


def _value(value: Any, name: str, default: Any = None) -> Any:
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _event_text(event: Any) -> str | None:
    content = _value(event, "content") or _value(_value(event, "config", {}), "content")
    parts = _value(content, "parts", []) if content else []
    if not parts:
        return None
    return _value(parts[0], "text")


class GoogleSessionStore:
    def __init__(self, settings: Settings, sessions: SessionApi | None = None, events: EventsApi | None = None):
        self.settings = settings
        if sessions is None or events is None:
            try:
                from vertexai import Client
            except ImportError as error:
                raise SessionStoreError("google-cloud-aiplatform をインストールしてください") from error
            client = Client(project=settings.project, location=settings.location)
            sessions, events = client.agent_engines.sessions, client.agent_engines.sessions.events
        self.sessions, self.events = sessions, events

    def create_session(self) -> str:
        try:
            created = self.sessions.create(name=self.settings.agent_engine, user_id=self.settings.user_id,
                config={"wait_for_completion": True})
            # google-cloud-aiplatform は AgentEngineSessionOperation を返す。
            # wait_for_completion 指定後の response が最終 Session である。
            created = _value(created, "response") or created
            name = _value(created, "name")
            if not name:
                raise SessionStoreError("Session Store がセッション名を返しませんでした")
            return name
        except Exception as error:
            raise SessionStoreError(f"Session Store セッションを作成できませんでした: {error}") from error

    def append_conversation(self, session_name: str, conversation: StoredConversation) -> None:
        items = [
            ("user", "user", conversation.user_prompt),
            ("claude", "assistant", conversation.assistant_response),
            ("adapter", "system", json.dumps({"schema_version": conversation.schema_version,
                "sample_version": SAMPLE_VERSION, "claude_session_id": conversation.claude_session_id,
                "nonce": conversation.nonce}, ensure_ascii=False, sort_keys=True)),
        ]
        self._append_text_events(session_name, items, "会話イベント")

    def append_tool_interaction(self, session_name: str, tool_name: str, tool_input: dict[str, Any],
                                tool_result: str) -> None:
        """SDK 固有形式に依存しない JSON 管理イベントとして tool call と結果を保存する。"""
        trace_version = "1"
        items = [
            ("tool-call", "system", json.dumps({
                "event_type": "tool_call", "schema_version": trace_version,
                "tool_name": tool_name, "input": tool_input,
            }, ensure_ascii=False, sort_keys=True)),
            ("tool-result", "system", json.dumps({
                "event_type": "tool_result", "schema_version": trace_version,
                "tool_name": tool_name, "result": tool_result,
            }, ensure_ascii=False, sort_keys=True)),
        ]
        self._append_text_events(session_name, items, "tool trace イベント")

    def _append_text_events(self, session_name: str, items: list[tuple[str, str, str]], label: str) -> None:
        try:
            for suffix, role, text in items:
                self.events.append(name=session_name, author="claude-session-store-verifier",
                    invocation_id=f"verify-{uuid.uuid4()}-{suffix}", timestamp=dt.datetime.now(dt.timezone.utc),
                    config={"content": {"role": role, "parts": [{"text": text}]}})
        except Exception as error:
            raise SessionStoreError(f"Session Store {label}を保存できませんでした: {error}") from error

    def delete_session(self, session_name: str) -> None:
        """検証で作成した Session Store セッションを明示的に削除する。"""
        try:
            self.sessions.delete(name=session_name)
        except Exception as error:
            raise SessionStoreError(f"Session Store セッションを削除できませんでした: {error}") from error

    def retrieve_conversation(self, session_name: str) -> StoredConversation:
        try:
            self.sessions.get(name=session_name)  # 新規作成は絶対に行わない
            events = list(self.events.list(name=session_name))
        except Exception as error:
            message = str(error)
            if "404" in message or "not found" in message.lower():
                raise SessionNotFoundError(f"指定されたセッションを取得できません: {session_name}") from error
            raise SessionStoreError(f"Session Store セッションを取得できませんでした: {error}") from error
        user_text = next((_event_text(e) for e in events if _event_text(e) and _value(_value(e, "content", {}), "role") == "user"), None)
        assistant_text = next((_event_text(e) for e in events if _event_text(e) and _value(_value(e, "content", {}), "role") == "assistant"), None)
        metadata = None
        for event in events:
            text = _event_text(event)
            if text:
                try:
                    candidate = json.loads(text)
                    if candidate.get("schema_version") and candidate.get("claude_session_id"):
                        metadata = candidate
                        break
                except json.JSONDecodeError:
                    pass
        missing = [name for name, value in (("初回ユーザー入力", user_text), ("Claude 応答", assistant_text),
                   ("管理情報", metadata), ("Claude セッション ID", metadata and metadata.get("claude_session_id")),
                   ("nonce", metadata and metadata.get("nonce"))) if not value]
        if missing:
            raise IncompleteSessionError("保存データが不完全です: " + ", ".join(missing))
        if metadata["schema_version"] != SCHEMA_VERSION:
            raise IncompleteSessionError(f"未対応の schema_version: {metadata['schema_version']}")
        return StoredConversation(metadata["claude_session_id"], metadata["nonce"], user_text, assistant_text, metadata["schema_version"])
