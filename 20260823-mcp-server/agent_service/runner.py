from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapter import ClaudeAgentAdapter, new_correlation_id
from .errors import ValidationError
from .models import InvocationEvidence
from .registry import RegistryResolver


class ValidationRunner:
    def __init__(self, resolver: RegistryResolver, adapter: ClaudeAgentAdapter):
        self.resolver = resolver
        self.adapter = adapter

    async def run(self, target: str, message: str, *, correlation_id: str | None = None) -> tuple[str, InvocationEvidence]:
        evidence = InvocationEvidence(correlation_id=correlation_id or new_correlation_id(), target=target)
        try:
            entry = self.resolver.resolve(target)
            evidence.service_id = entry.service_id
            evidence.endpoint_id = entry.endpoint_id
            evidence.validated_host = entry.host
            result = await self.adapter.invoke(entry, message, evidence)
            return result, evidence
        except ValidationError:
            raise

    @staticmethod
    def write_evidence(path: Path, evidence: InvocationEvidence, *, status: str) -> None:
        payload: dict[str, Any] = {"status": status, **evidence.sanitized()}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
