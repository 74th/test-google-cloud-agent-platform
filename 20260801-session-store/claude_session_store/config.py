from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


class ConfigurationError(ValueError):
    pass


VERTEX_HAIKU_4_5_MODEL = "claude-haiku-4-5@20251001"


@dataclass(frozen=True)
class Settings:
    project: str
    location: str
    agent_engine: str
    user_id: str
    claude_cwd: Path
    vertex_location: str
    model: str = VERTEX_HAIKU_4_5_MODEL

    @classmethod
    def from_env(cls) -> "Settings":
        # 開発環境ではプロジェクト直下の .env を読み込む。既存の環境変数を優先する。
        load_dotenv(find_dotenv(usecwd=True), override=False)
        names = {
            "project": "GOOGLE_CLOUD_PROJECT", "location": "GOOGLE_CLOUD_LOCATION",
            "agent_engine": "GOOGLE_CLOUD_AGENT_ENGINE", "user_id": "SESSION_STORE_USER_ID",
            "claude_cwd": "CLAUDE_SESSION_CWD", "vertex_location": "VERTEX_AI_LOCATION",
        }
        values = {field: os.environ.get(env, "").strip() for field, env in names.items()}
        missing = [env for field, env in names.items() if not values[field]]
        if missing:
            raise ConfigurationError("必須環境変数が不足しています: " + ", ".join(missing))
        return cls(
            project=values["project"], location=values["location"],
            agent_engine=values["agent_engine"], user_id=values["user_id"],
            claude_cwd=Path(values["claude_cwd"]).resolve(),
            vertex_location=values["vertex_location"],
        )
