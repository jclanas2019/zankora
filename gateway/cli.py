from __future__ import annotations
import json, uuid, asyncio
from datetime import datetime
import typer
import httpx
from rich import print
from rich.table import Table

app = typer.Typer(help="Zankora Gateway CLI - Control plane client for the Zankora secure agent orchestration gateway.")

def _ws_url(host: str, port: int) -> str:
    return f"ws://{host}:{port}/ws"

def _http_url(host: str, port: int, path: str) -> str:
    return f"http://{host}:{port}{path}"

@app.command()
def doctor(host: str = "127.0.0.1", port: int = 8787, api_key: str = typer.Option("", envvar="AGW_CLIENT_KEY")):
    """Run a configuration audit via WS."""
    import websockets

    async def _run():
        headers = {"x-api-key": api_key} if api_key else {}
        async with websockets.connect(_ws_url(host, port), additional_headers=headers) as ws:
            req = {"type":"req:doctor.audit","id":uuid.uuid4().hex,"ts":datetime.utcnow().isoformat()+"Z","payload":{}}
            await ws.send(json.dumps(req))
            res = json.loads(await ws.recv())
            print(res)
    asyncio.run(_run())

@app.command()
def channels(host: str = "127.0.0.1", port: int = 8787, api_key: str = typer.Option("", envvar="AGW_CLIENT_KEY")):
    """List all channels."""
    import websockets
    async def _run():
        headers = {"x-api-key": api_key} if api_key else {}
        async with websockets.connect(_ws_url(host, port), additional_headers=headers) as ws:
            req = {"type":"req:channels.list","id":uuid.uuid4().hex,"ts":datetime.utcnow().isoformat()+"Z","payload":{}}
            await ws.send(json.dumps(req))
            res = json.loads(await ws.recv())
            chans = res.get("payload", {}).get("channels", [])
            t = Table(title="Channels")
            t.add_column("id"); t.add_column("type"); t.add_column("status"); t.add_column("last_seen")
            for c in chans:
                t.add_row(c["id"], c["type"], c["status"], str(c.get("last_seen")))
            print(t)
    asyncio.run(_run())

@app.command()
def chats(
    channel_id: str = None,
    host: str = "127.0.0.1",
    port: int = 8787,
    api_key: str = typer.Option("", envvar="AGW_CLIENT_KEY"),
):
    """List all chats, optionally filtered by channel."""
    import websockets
    async def _run():
        headers = {"x-api-key": api_key} if api_key else {}
        async with websockets.connect(_ws_url(host, port), additional_headers=headers) as ws:
            req = {"type":"req:chat.list","id":uuid.uuid4().hex,"ts":datetime.utcnow().isoformat()+"Z",
                   "payload":{"channel_id": channel_id} if channel_id else {}}
            await ws.send(json.dumps(req))
            res = json.loads(await ws.recv())
            chats_list = res.get("payload", {}).get("chats", [])
            t = Table(title="Chats")
            t.add_column("chat_id"); t.add_column("channel_id"); t.add_column("participants")
            for c in chats_list:
                t.add_row(c["chat_id"], c["channel_id"], str(c.get("participants", [])))
            print(t)
    asyncio.run(_run())

@app.command()
def run(
    chat_id: str,
    channel_id: str = "webchat-1",
    prompt: str = "hola",
    host: str = "127.0.0.1",
    port: int = 8787,
    api_key: str = typer.Option("", envvar="AGW_CLIENT_KEY"),
    tail: bool = True,
):
    """Run an agent with a prompt."""
    import websockets
    async def _run():
        headers = {"x-api-key": api_key} if api_key else {}
        async with websockets.connect(_ws_url(host, port), additional_headers=headers) as ws:
            # send run request
            rid = uuid.uuid4().hex
            req = {"type":"req:agent.run","id":rid,"ts":datetime.utcnow().isoformat()+"Z",
                   "payload":{"chat_id":chat_id,"channel_id":channel_id,"prompt":prompt,"requested_by":"cli"}}
            await ws.send(json.dumps(req))
            res = json.loads(await ws.recv())
            print(res)
            run_id = res.get("payload", {}).get("run", {}).get("run_id")
            if not tail or not run_id:
                return
            print(f"[bold]Tailing events for {run_id}[/bold] (Ctrl+C to stop)")
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("type","").startswith("evt:"):
                    if msg.get("payload", {}).get("run_id") in (None, run_id):
                        print(msg)
                if msg.get("type") == "evt:run.completed" and msg.get("payload", {}).get("run_id") == run_id:
                    break
    asyncio.run(_run())

@app.command()
def approve(
    run_id: str,
    host: str = "127.0.0.1",
    port: int = 8787,
    api_key: str = typer.Option("", envvar="AGW_CLIENT_KEY"),
):
    """Grant approval for a pending tool execution."""
    import websockets
    async def _run():
        headers = {"x-api-key": api_key} if api_key else {}
        async with websockets.connect(_ws_url(host, port), additional_headers=headers) as ws:
            req = {"type":"req:approval.grant","id":uuid.uuid4().hex,"ts":datetime.utcnow().isoformat()+"Z",
                   "payload":{"run_id": run_id}}
            await ws.send(json.dumps(req))
            res = json.loads(await ws.recv())
            print(res)
    asyncio.run(_run())

@app.command()
def events(
    run_id: str = None,
    after_seq: int = None,
    host: str = "127.0.0.1",
    port: int = 8787,
    api_key: str = typer.Option("", envvar="AGW_CLIENT_KEY"),
):
    """Tail recent events, optionally filtered by run_id."""
    import websockets
    async def _run():
        headers = {"x-api-key": api_key} if api_key else {}
        async with websockets.connect(_ws_url(host, port), additional_headers=headers) as ws:
            req = {"type":"req:runs.tail","id":uuid.uuid4().hex,"ts":datetime.utcnow().isoformat()+"Z",
                   "payload":{"run_id": run_id, "after_seq": after_seq}}
            await ws.send(json.dumps(req))
            res = json.loads(await ws.recv())
            print(res)
    asyncio.run(_run())

@app.command()
def config_get(
    host: str = "127.0.0.1",
    port: int = 8787,
    api_key: str = typer.Option("", envvar="AGW_CLIENT_KEY"),
):
    """Get current configuration."""
    import websockets
    async def _run():
        headers = {"x-api-key": api_key} if api_key else {}
        async with websockets.connect(_ws_url(host, port), additional_headers=headers) as ws:
            req = {"type":"req:config.get","id":uuid.uuid4().hex,"ts":datetime.utcnow().isoformat()+"Z","payload":{}}
            await ws.send(json.dumps(req))
            res = json.loads(await ws.recv())
            print(res)
    asyncio.run(_run())

@app.command()
def config_set(
    allowlist_json: str = "{}",
    tool_allow_json: str = "{}",
    dm_policy: str = "",
    group_policy: str = "",
    host: str = "127.0.0.1",
    port: int = 8787,
    api_key: str = typer.Option("", envvar="AGW_CLIENT_KEY"),
):
    """Set configuration."""
    import websockets
    async def _run():
        payload = {"policy": {}}
        if allowlist_json != "{}":
            payload["policy"]["allowlist"] = json.loads(allowlist_json)
        if tool_allow_json != "{}":
            payload["policy"]["tool_allow"] = json.loads(tool_allow_json)
        if dm_policy:
            payload["policy"]["dm_policy"] = dm_policy
        if group_policy:
            payload["policy"]["group_policy"] = group_policy
        headers = {"x-api-key": api_key} if api_key else {}
        async with websockets.connect(_ws_url(host, port), additional_headers=headers) as ws:
            req = {"type":"req:config.set","id":uuid.uuid4().hex,"ts":datetime.utcnow().isoformat()+"Z","payload":payload}
            await ws.send(json.dumps(req))
            res = json.loads(await ws.recv())
            print(res)
    asyncio.run(_run())

def main():
    """Entry point for the CLI."""
    app()
