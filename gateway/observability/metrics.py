from __future__ import annotations
from prometheus_client import Counter, Histogram, Gauge

ws_connections = Gauge("agw_ws_connections", "Active WebSocket control-plane connections")
rpc_requests = Counter("agw_rpc_requests_total", "RPC requests total", ["method"])
rpc_errors = Counter("agw_rpc_errors_total", "RPC errors total", ["method", "code"])
agent_runs = Counter("agw_agent_runs_total", "Agent runs total", ["status"])
agent_run_latency = Histogram("agw_agent_run_latency_seconds", "Agent run latency seconds")
inbound_messages = Counter("agw_inbound_messages_total", "Inbound channel messages", ["channel_type"])
blocked_actions = Counter("agw_blocked_actions_total", "Blocked actions", ["reason"])
