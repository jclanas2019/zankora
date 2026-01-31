import pytest, asyncio
from gateway.server.ws import WSRouter

@pytest.mark.asyncio
async def test_ws_router_unknown_method():
    router = WSRouter(handler_map={})
    res = await router.handle({"type":"req:channels.list","id":"1","ts":"2026-01-30T00:00:00Z","payload":{}})
    assert res["ok"] is False
    assert res["err"]["code"] == "no_such_method"

@pytest.mark.asyncio
async def test_ws_router_ok():
    async def handler(payload): return {"x": 1}
    router = WSRouter(handler_map={"req:hello": handler})
    res = await router.handle({"type":"req:hello","id":"1","ts":"2026-01-30T00:00:00Z","payload":{}})
    assert res["ok"] is True
    assert res["payload"]["x"] == 1
