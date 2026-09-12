"""Small JSON Lines logger intentionally excluding request bodies and headers."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("byoc_runtime")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def event(name: str, *, request_id: str, started: float, severity: str = "INFO", **fields: Any) -> None:
    payload = {"timestamp": datetime.now(UTC).isoformat(), "severity": severity, "event": name,
               "request_id": request_id, "elapsed_ms": round((time.monotonic() - started) * 1000, 1), **fields}
    logger.info(json.dumps(payload, ensure_ascii=False, sort_keys=True))
