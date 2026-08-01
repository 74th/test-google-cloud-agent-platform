from __future__ import annotations

import secrets

from .claude import ClaudeRunner
from .models import StoredConversation, VerificationResult
from .session_store import GoogleSessionStore


def start(store: GoogleSessionStore, claude: ClaudeRunner) -> VerificationResult:
    result = VerificationResult()
    try:
        session_name = store.create_session()
        result.session_created, result.session_name = True, session_name
    except Exception as error:
        result.fail("session_created", error); return result
    nonce = secrets.token_urlsafe(18)
    prompt = f"この検証値を覚えてください: {nonce}\n応答は値だけを返してください。"
    try:
        claude_session_id, response = __import__("asyncio").run(claude.run(prompt))
        store.append_conversation(session_name, StoredConversation(claude_session_id, nonce, prompt, response))
        result.events_appended = True
    except Exception as error:
        result.fail("events_appended", error)
    return result


def resume(store: GoogleSessionStore, claude: ClaudeRunner, session_name: str) -> VerificationResult:
    result = VerificationResult(session_name=session_name)
    try:
        conversation = store.retrieve_conversation(session_name)
        # 必須の三イベントを検証済みであるため、初回プロセス側の作成・保存も確認できる。
        result.session_created = True
        result.events_appended = True
        result.events_retrieved = True
    except Exception as error:
        result.fail("events_retrieved", error); return result
    try:
        _, response = __import__("asyncio").run(claude.run(
            "前回の検証値を、説明なしで値だけ返してください。", resume=conversation.claude_session_id))
        result.claude_resumed = True
        result.nonce_matched = response.strip() == conversation.nonce.strip()
        if not result.nonce_matched:
            result.error_stage, result.error_type = "nonce_matched", "NonceMismatch"
            result.error_message = "Claude の回答が保存済み nonce と一致しません"
    except Exception as error:
        result.fail("claude_resumed", error)
    return result
