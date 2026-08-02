import asyncio

import pytest

from byoc_runtime.agent import DummyAgent


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["query", "async_query"])
async def test_unary_methods_wait_then_return_ok(method):
    fake = FakeTime()
    agent = DummyAgent(sleep=fake.sleep, clock=lambda: fake.now)
    assert await getattr(agent, method)() == "OK"
    assert fake.sleeps == [10]


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["stream_query", "async_stream_query"])
async def test_stream_methods_emit_ordered_chunks(method):
    fake = FakeTime()
    agent = DummyAgent(sleep=fake.sleep, clock=lambda: fake.now)
    chunks = [chunk async for chunk in getattr(agent, method)()]
    assert chunks == ["Streaming OK", "OK"]
    assert fake.sleeps == [5, 5]


@pytest.mark.asyncio
async def test_async_query_does_not_block_other_tasks():
    agent = DummyAgent(sleep=lambda _: asyncio.sleep(0))
    completed = False

    async def marker():
        nonlocal completed
        await asyncio.sleep(0)
        completed = True

    await asyncio.gather(agent.async_query(), marker())
    assert completed
