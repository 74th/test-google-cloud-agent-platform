from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SCHEMA_VERSION = "1"
SAMPLE_VERSION = "0.1.0"


@dataclass(frozen=True)
class StoredConversation:
    claude_session_id: str
    nonce: str
    user_prompt: str
    assistant_response: str
    schema_version: str = SCHEMA_VERSION


@dataclass
class VerificationResult:
    session_created: bool = False
    events_appended: bool = False
    events_retrieved: bool = False
    claude_resumed: bool = False
    nonce_matched: bool = False
    session_name: str | None = None
    error_stage: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    constraints: list[str] = field(default_factory=lambda: [
        "Claude Agent SDK の resume は同一ローカル環境にあるトランスクリプトを必要とする。",
        "Session Store は Claude のローカルトランスクリプトやワークスペースを代替しない。",
    ])

    @property
    def success(self) -> bool:
        return all((self.session_created, self.events_appended, self.events_retrieved,
                    self.claude_resumed, self.nonce_matched))

    def fail(self, stage: str, error: Exception) -> None:
        self.error_stage = stage
        self.error_type = type(error).__name__
        self.error_message = str(error)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["success"] = self.success
        return data
