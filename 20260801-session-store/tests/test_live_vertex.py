"""明示指定時だけ実行する、Vertex AI 上の Claude Agent SDK の統合テスト。"""

from __future__ import annotations

import asyncio
import os
import secrets

import pytest

from claude_session_store.claude import AgentSdkRunner
from claude_session_store.config import Settings


pytestmark = pytest.mark.live_vertex


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_VERTEX_TESTS") != "1",
    reason="Vertex AI の課金対象テスト。RUN_LIVE_VERTEX_TESTS=1 を指定した場合だけ実行する。",
)
def test_session_resumes_across_three_live_turns():
    """初回と二回の再開で、Claude の同一ローカルセッションが継続することを確認する。"""
    settings = Settings.from_env()
    runner = AgentSdkRunner(settings)
    nonce = secrets.token_urlsafe(18)

    session_id, first_response = asyncio.run(runner.run(
        f"検証トークンを覚えてください: {nonce}\n応答はトークンだけにしてください。"
    ))
    assert first_response.strip() == nonce

    resumed_session_id, second_response = asyncio.run(runner.run(
        "最初のターンで覚えるよう求めた検証トークンを、説明なしで返してください。",
        resume=session_id,
    ))
    assert resumed_session_id == session_id
    assert second_response.strip() == nonce

    final_session_id, third_response = asyncio.run(runner.run(
        "同じ検証トークンをもう一度、説明なしで返してください。",
        resume=session_id,
    ))
    assert final_session_id == session_id
    assert third_response.strip() == nonce
