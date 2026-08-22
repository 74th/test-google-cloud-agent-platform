"""Deliberately slow, event-loop-friendly agent used for transport verification."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable

from .models import DEFAULT_DELAY_SECONDS

Sleep = Callable[[float], Awaitable[object]]
Clock = Callable[[], float]


class DummyAgent:
    def __init__(self, *, sleep: Sleep = asyncio.sleep, clock: Clock = time.monotonic) -> None:
        self._sleep = sleep
        self._clock = clock

    async def query(self, delay_seconds: int = DEFAULT_DELAY_SECONDS) -> str:
        await self._sleep(delay_seconds)
        return "OK"

    async def async_query(self, delay_seconds: int = DEFAULT_DELAY_SECONDS) -> str:
        await self._sleep(delay_seconds)
        return "OK"

    async def stream_query(self) -> AsyncIterator[str]:
        await self._sleep(5)
        yield "Streaming OK"
        await self._sleep(5)
        yield "OK"

    async def async_stream_query(self) -> AsyncIterator[str]:
        await self._sleep(5)
        yield "Streaming OK"
        await self._sleep(5)
        yield "OK"
