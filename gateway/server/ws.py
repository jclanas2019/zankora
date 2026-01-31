from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from gateway.protocol.ws_models import WSRequest
from gateway.observability.logging import get_logger
from gateway.observability import metrics

log = get_logger("ws")


def now() -> datetime:
    return datetime.utcnow()


def ws_msg(
    type_: str,
    id_: str | None = None,
    payload: dict[str, Any] | None = None,
    ok: bool = True,
    err: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "type": type_,
        "id": id_ or uuid.uuid4().hex,
        "ts": now().isoformat() + "Z",
        "payload": payload or {},
    }
    if type_.startswith("res:"):
        base["ok"] = ok
        base["err"] = err
    return base


@dataclass
class ClientState:
    """
    Per-WebSocket connection state.
    If subscribed_run_ids is empty -> send ALL events (backward compatible).
    If it has values -> send ONLY events for those run_ids.
    """
    subscribed_run_ids: set[str] = field(default_factory=set)


class WSRouter:
    def __init__(self, handler_map: dict[str, Callable[..., Awaitable[dict[str, Any]]]]):
        self.handler_map = handler_map

    async def handle(self, req: dict[str, Any]) -> dict[str, Any]:
        try:
            parsed = WSRequest.model_validate(req)
        except Exception as e:
            return ws_msg(
                "res:error",
                id_=req.get("id") or uuid.uuid4().hex,
                ok=False,
                err={"code": "bad_request", "message": str(e)},
            )

        handler = self.handler_map.get(parsed.type)
        if not handler:
            return ws_msg(
                f"res:{parsed.type.split(':', 1)[1]}",
                id_=parsed.id,
                ok=False,
                err={"code": "no_such_method", "message": parsed.type},
            )

        metrics.rpc_requests.labels(method=parsed.type).inc()
        try:
            out = await handler(parsed.payload)
            return ws_msg(f"res:{parsed.type.split(':', 1)[1]}", id_=parsed.id, payload=out, ok=True)
        except Exception as e:
            metrics.rpc_errors.labels(method=parsed.type, code="internal").inc()
            log.exception("rpc_failed", method=parsed.type, err=str(e))
            return ws_msg(
                f"res:{parsed.type.split(':', 1)[1]}",
                id_=parsed.id,
                ok=False,
                err={"code": "internal", "message": "rpc_failed"},
            )


async def pump_events(ws: WebSocket, bus, stop_event: asyncio.Event, state: ClientState) -> None:
    """
    Server-push event stream.
    IMPORTANT: emits `evt:*` types per protocol.
    Also filters by run_id if the client subscribed.
    """
    sub = bus.subscribe()
    try:
        async for evt in bus.iter(sub):
            if stop_event.is_set():
                break

            # Filter: if subscribed_run_ids is non-empty, only send those runs
            if state.subscribed_run_ids and evt.run_id not in state.subscribed_run_ids:
                continue

            msg = {
                "type": f"evt:{evt.type.value}",  # ✅ protocol-correct
                "id": f"evt_{evt.seq}",
                "ts": evt.ts.isoformat() + "Z",
                "payload": {
                    "run_id": evt.run_id,
                    "seq": evt.seq,
                    **(evt.payload or {}),
                },
            }
            await ws.send_text(json.dumps(msg))
    finally:
        bus.unsubscribe(sub)


async def serve_ws(ws: WebSocket, router: WSRouter, bus) -> None:
    await ws.accept()
    metrics.ws_connections.inc()

    stop = asyncio.Event()
    state = ClientState()

    pump_task = asyncio.create_task(pump_events(ws, bus, stop, state))

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                await ws.send_text(
                    json.dumps(ws_msg("res:error", ok=False, err={"code": "bad_json", "message": "invalid json"}))
                )
                continue

            # Parse request early to update per-connection subscription
            try:
                parsed = WSRequest.model_validate(data)
            except Exception:
                res = await router.handle(data)
                await ws.send_text(json.dumps(res))
                continue

            # ✅ Side-effect: subscribing the connection to a run_id when runs.tail is requested
            # This keeps the protocol the same (still returns events in response),
            # but also ensures live stream is filtered and useful.
            if parsed.type == "req:runs.tail":
                run_id = (parsed.payload or {}).get("run_id")
                if run_id:
                    state.subscribed_run_ids.add(run_id)

            res = await router.handle(data)
            await ws.send_text(json.dumps(res))

    except WebSocketDisconnect:
        return
    finally:
        stop.set()
        pump_task.cancel()
        metrics.ws_connections.dec()
