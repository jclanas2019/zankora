# Arquitectura

## Diagrama textual

```
+---------------------+          +-------------------+
|  CLI / UI (WS RPC)  |<-------->|  WS Control Plane  |
+---------------------+          |  (FastAPI WS)      |
                                 +---------+---------+
                                           |
                                           v
                                 +-------------------+
                                 |  Gateway Core     |  (single authority)
                                 |  - Channel owner  |
                                 |  - Policy engine  |
                                 |  - Agent runs     |
                                 |  - Plugin registry|
                                 +----+----+----+----+
                                      |    |    |
                      inbound events  |    |    |  tool calls
                                      |    |    v
                                      |    |  +----------------+
                                      |    |  | Tool Registry   |
                                      |    |  | + Plugins       |
                                      |    |  +----------------+
                                      |    |
                                      v    v
                              +-------------------+
                              |  EventBus (async) |
                              +---------+---------+
                                        |
                                        v
                          +--------------------------+
                          |  Subscribers             |
                          | - WS clients (events)    |
                          | - channels (optional)    |
                          +--------------------------+

Channels:
  +-------------------+      +-------------------+
  | Telegram Adapter  |      | WhatsApp Adapter  |
  +-------------------+      +-------------------+
            \                      //
             \                    //
              v                  v
                 +----------------+
                 | InboundEnvelope|
                 +----------------+

Persistence:
  SQLite (async SQLAlchemy):
    channels, chats, messages, agent_runs, events
```

## Módulos

- `gateway/core/gateway.py`: autoridad única, coordina ingest, runs, events, persistence.
- `gateway/server/app.py`: FastAPI app, endpoints health/metrics, WS endpoint.
- `gateway/server/ws.py`: router RPC WS + pump server-push de eventos.
- `gateway/agent/*`: loop de agente agnóstico del LLM (MockLLM incluido).
- `gateway/channels/*`: adapters (webchat minimal + skeletons telegram/whatsapp).
- `gateway/plugins/*`: loader + registry.
- `gateway/security/*`: policy engine, rate limit, sanitización, auth.
- `gateway/persistence/*`: schema + repo + init.
- `gateway/observability/*`: logs JSON, métricas Prometheus.

## Flujo end-to-end

1. Canal ingresa `InboundEnvelope` → `Gateway.ingest_inbound`.
2. Gateway sanitiza, aplica `PolicyEngine`, persiste `Message`, emite `evt:message.inbound`.
3. Cliente dispara `req:agent.run` → Gateway crea `AgentRun`, build context, crea task async.
4. `AgentRunner` planifica (LLMAdapter), ejecuta tools (con policy/approval), emite eventos streaming.
5. Persistencia de `AgentRun` y `Event` para tailing, y eventos live por EventBus.

