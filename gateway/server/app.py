from __future__ import annotations
import json
from fastapi import FastAPI, WebSocket, Depends, Header
from fastapi.responses import HTMLResponse, PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from gateway.config import Settings, load_settings
from gateway.persistence.db import make_engine, make_session_factory
from gateway.persistence.migrations import init_db
from gateway.core.gateway import Gateway
from gateway.server.ws import WSRouter, serve_ws
from gateway.security.auth import verify_client_key
from gateway.observability.logging import configure_logging, get_logger
from gateway.observability import metrics

log = get_logger("app")

def create_app(settings: Settings) -> FastAPI:
    configure_logging(settings.log_level, settings.json_logs)
    app = FastAPI(title="Agent Gateway", version="0.1.0")

    engine = make_engine(settings)
    session_factory = make_session_factory(engine)
    gateway = Gateway(settings, engine, session_factory)

    @app.on_event("startup")
    async def _startup():
        await init_db(engine)
        await gateway.start()
        log.info("gateway_started", host=settings.host, port=settings.port)

    @app.on_event("shutdown")
    async def _shutdown():
        await gateway.stop()
        await engine.dispose()

    async def _auth(x_api_key: str | None = Header(default=None)):
        if not verify_client_key(settings, x_api_key):
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="unauthorized")
        return True

    # health/metrics
    @app.get(settings.health_path)
    async def healthz():
        return {"ok": True, "service": "agent-gateway", "version": "0.1.0"}

    @app.get(settings.metrics_path)
    async def metrics_endpoint():
        return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

    # Minimal webchat UI
    @app.get("/", response_class=HTMLResponse)
    async def webchat_index():
        html = (open("webchat/index.html", "r", encoding="utf-8").read())
        return HTMLResponse(content=html)

    # Control-plane WS (RPC + server push)
    router = WSRouter(handler_map={
        "req:hello": lambda payload: hello(payload, settings),
        "req:channels.list": lambda payload: channels_list(payload, gateway),
        "req:chat.list": lambda payload: chat_list(payload, gateway),
        "req:chat.messages": lambda payload: chat_messages(payload, gateway),
        "req:agent.run": lambda payload: agent_run(payload, gateway),
        "req:runs.tail": lambda payload: runs_tail(payload, gateway),
        "req:config.get": lambda payload: config_get(payload, gateway),
        "req:config.set": lambda payload: config_set(payload, gateway),
        "req:doctor.audit": lambda payload: doctor_audit(payload, settings, gateway),
        "req:approval.grant": lambda payload: approval_grant(payload, gateway),
    })

    @app.websocket(settings.ws_path)
    async def ws_endpoint(ws: WebSocket, _=Depends(_auth)):
        await serve_ws(ws, router, gateway.bus)

    return app

async def hello(payload, settings: Settings):
    return {
        "server": "agent-gateway",
        "version": "0.1.0",
        "instance_id": settings.instance_id,
        "features": ["rpc_ws", "event_stream", "plugins", "sqlite", "deny_by_default"],
    }

async def channels_list(payload, gateway: Gateway):
    chans = await gateway.list_channels()
    return {"channels": [c.model_dump(mode="json") for c in chans]}

async def chat_list(payload, gateway: Gateway):
    channel_id = payload.get("channel_id")
    chats = await gateway.list_chats(channel_id=channel_id)
    return {"chats": [c.model_dump(mode="json") for c in chats]}

async def chat_messages(payload, gateway: Gateway):
    chat_id = payload["chat_id"]
    limit = int(payload.get("limit", 50))
    msgs = await gateway.list_messages(chat_id=chat_id, limit=limit)
    return {"messages": [m.model_dump(mode="json") for m in msgs]}

async def agent_run(payload, gateway: Gateway):
    run = await gateway.start_run(
        chat_id=payload["chat_id"],
        channel_id=payload["channel_id"],
        requested_by=payload.get("requested_by", "client"),
        prompt=payload["prompt"],
    )
    return {"run": run.model_dump(mode="json")}

async def runs_tail(payload, gateway: Gateway):
    run_id = payload.get("run_id")
    after_seq = payload.get("after_seq")
    after_seq = int(after_seq) if after_seq is not None else None
    evts = await gateway.tail_events(run_id=run_id, after_seq=after_seq)
    return {"events": [e.model_dump(mode="json") for e in evts]}

async def config_get(payload, gateway: Gateway):
    # MVP: only policy for now
    return {"policy": gateway.policy.model_dump(mode="json"), "tools": [t.model_dump() for t in gateway.tools.list_specs()]}

async def config_set(payload, gateway: Gateway):
    # MVP: allow updating allowlist and tool_allow only (validate shape)
    pol = payload.get("policy") or {}
    if "allowlist" in pol:
        gateway.policy.allowlist = pol["allowlist"]
    if "tool_allow" in pol:
        gateway.policy.tool_allow = pol["tool_allow"]
    if "dm_policy" in pol:
        gateway.policy.dm_policy = pol["dm_policy"]
    if "group_policy" in pol:
        gateway.policy.group_policy = pol["group_policy"]
    return {"ok": True}

async def approval_grant(payload, gateway: Gateway):
    run_id = payload["run_id"]
    ok = await gateway.grant_approval(run_id)
    return {"ok": ok}

async def doctor_audit(payload, settings: Settings, gateway: Gateway):
    findings = []
    if settings.host == "0.0.0.0" and settings.require_client_auth:
        findings.append({"severity":"high","issue":"gateway_exposed","detail":"host=0.0.0.0. Ensure firewall + TLS + auth."})
    if not settings.client_api_keys and settings.require_client_auth:
        findings.append({"severity":"critical","issue":"no_client_api_keys","detail":"require_client_auth enabled but no keys configured."})
    if not gateway.policy.allowlist:
        findings.append({"severity":"high","issue":"allowlist_empty","detail":"Deny-by-default means all inbound is blocked; if unintended configure allowlist."})
    # write tools without approvals (if configured off)
    if not settings.require_approvals_for_write_tools:
        findings.append({"severity":"high","issue":"write_tools_no_approval","detail":"Write tools can execute without approvals. Recommended ON."})
    if not settings.json_logs:
        findings.append({"severity":"medium","issue":"non_json_logs","detail":"Prefer JSON logs for 24/7 ops."})
    # plugin signature is out of scope; warn
    if gateway.loaded_plugins:
        findings.append({"severity":"low","issue":"plugins_unsigned","detail":"Plugins are local code. Consider signing/allowlisting plugin hashes."})
    return {"findings": findings, "suggestions": [
        "Terminate TLS at a reverse proxy (Caddy/Nginx) and keep WS behind auth.",
        "Use separate API keys for human operators vs automation clients.",
        "Run gateway with least privilege OS user; restrict data_dir permissions.",
        "Rotate secrets and store in a secret manager in prod.",
    ]}
