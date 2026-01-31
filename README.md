# 🚀 Zankora — Agent Gateway
Production-Ready Multi-Channel AI Agent System

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-production--ready-brightgreen.svg)

**Zankora is a unified, secure, and extensible gateway for AI agents, designed for real-world, enterprise-grade deployments.**

</div>

---

## 🌟 What is Zankora?

**Zankora** is a **centralized Agent Gateway** that orchestrates AI agents across multiple communication channels, enforces security and policy controls, and provides full observability over agent behavior.

It is designed around a **Single Authority** principle: all state, decisions, approvals, and events flow through one core system, making agent behavior auditable, controllable, and production-safe.

Zankora is ideal for:
- Enterprise AI assistants
- Multi-channel conversational agents
- Tool-augmented LLM systems
- Regulated or security-sensitive environments

---

## 🌟 Features

### Core Capabilities
- **🔌 Multi-Channel Support**: Telegram, WhatsApp Business, WebChat, extensible via plugins
- **🎯 Single Authority Architecture**: Centralized state, policy, and run coordination
- **🔄 Real-Time Control Plane**: WebSocket-based RPC with server-push events
- **🧩 Plugin System**: Hot-load tools, channels, and integrations
- **🛡️ Security by Default**: Allow-list policies, rate limits, approval workflows
- **📊 Enterprise Observability**: Structured logs, Prometheus metrics, audit events
- **💾 Persistent State**: SQLite (dev) / PostgreSQL (production)
- **⚙️ Production Hardened**: Health checks, graceful shutdown, retries, circuit breakers

### Advanced Features
- Exponential backoff retries for transient failures
- Circuit breaker protection for external services
- Human-in-the-loop approval workflows
- Multi-LLM support (Anthropic, OpenAI, Mock)
- Token bucket rate limiting (per channel / user)
- Distributed tracing via run_id propagation
- Input validation and sanitization
- Hot-reload plugin loading at startup

---

## 🏗️ Architecture

Zankora separates **control**, **execution**, and **integration** concerns:

```
┌─────────────────────┐          ┌───────────────────┐
│  CLI / UI (WS RPC)  │◄────────►│  WS Control Plane │
└─────────────────────┘          │  (FastAPI WS)     │
                                 └──────────┬────────┘
                                            │
                                            ▼
                                 ┌───────────────────┐
                                 │  Zankora Core     │
                                 │  ──────────────── │
                                 │  • Channels       │
                                 │  • Policies       │
                                 │  • Agent Runs     │
                                 │  • Plugins        │
                                 └────┬─────┬────┬───┘
                                      │     │    │
                  Inbound Events      │     │    │  Tool Calls
                                      │     │    ▼
                                      │     │  ┌──────────────┐
                                      │     │  │ Tool Registry│
                                      │     │  │ + Plugins    │
                                      │     │  └──────────────┘
                                      │     │
                                      ▼     ▼
                              ┌──────────────────┐
                              │  Event Bus       │
                              │  (async pub/sub) │
                              └────────┬─────────┘
                                       │
                                       ▼
                          ┌──────────────────────────┐
                          │  Subscribers             │
                          │  • WS clients            │
                          │  • Channel adapters      │
                          │  • Audit logs            │
                          └──────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- pip or uv

### Installation

```bash
git clone <repository-url>
cd zankora

python -m venv .venv
source .venv/bin/activate

pip install -e .[all]
```

```
======================================================================
                         ZANKORA GATEWAY
                    Command Line Reference
======================================================================


1) zankora-gateway
------------------
Servidor principal de Zankora.
Levanta el Gateway (FastAPI + WebSocket Control Plane).

USO:
    zankora-gateway

DESCRIPCION:
    - Inicia el servidor HTTP + WebSocket
    - Carga configuración desde variables de entorno (.env)
    - Inicializa canales, plugins, políticas y persistencia

NO ACEPTA SUBCOMANDOS

VARIABLES DE ENTORNO COMUNES:
    AGW_HOST
    AGW_PORT
    AGW_INSTANCE_ID
    AGW_LOG_LEVEL
    AGW_LOG_FORMAT
    AGW_DATA_DIR
    AGW_PLUGIN_DIR


======================================================================


2) zankora
----------
CLI de control para operar Zankora vía WebSocket RPC.
Cliente del Control Plane.

ALIAS:
    zankora
    agw                (alias legacy / corto)

USO GENERAL:
    zankora <comando> [opciones]


COMANDOS DISPONIBLES
-------------------

1. doctor
---------
Ejecuta auditoría completa del sistema.

USO:
    zankora doctor

DESCRIPCION:
    - Verifica base de datos
    - Verifica event bus
    - Verifica canales
    - Verifica plugins
    - Verifica rate limiter
    - Verifica lockfile


2. channels
-----------
Lista los canales activos.

USO:
    zankora channels

SALIDA TIPICA:
    webchat-1     READY
    telegram-1    READY
    whatsapp-1    DISABLED


3. chats
--------
Lista los chats conocidos.

USO:
    zankora chats
    zankora chats --channel-id telegram-1

OPCIONES:
    --channel-id <id>


4. run
------
Ejecuta un run de agente sobre un chat.

USO:
    zankora run <chat_id> --prompt "<texto>"

EJEMPLO:
    zankora run chat_demo_1 --prompt "Hola, ¿en qué me ayudas?"

COMPORTAMIENTO:
    - Crea run_id
    - Ejecuta agente
    - Emite eventos en tiempo real
    - Puede requerir aprobación si usa write tools


5. approve
----------
Aprueba una operación pendiente (human-in-the-loop).

USO:
    zankora approve <run_id>

EJEMPLO:
    zankora approve run_xyz123


6. events
---------
Muestra eventos asociados a un run.

USO:
    zankora events <run_id>
    zankora events <run_id> --after-seq <n>

OPCIONES:
    --after-seq <numero>


7. config-get
-------------
Obtiene la configuración actual del gateway.

USO:
    zankora config-get


8. config-set
-------------
Actualiza configuración dinámica.

USO:
    zankora config-set <opciones>

EJEMPLOS:
    zankora config-set --allowlist-json '{"telegram-1":["user123"]}'
    zankora config-set --tool-allow-json '{"core.echo":true}'


======================================================================


OPCIONES GLOBALES (TODOS LOS COMANDOS)
-------------------------------------

    --host <host>        (default: 127.0.0.1)
    --port <port>        (default: 8787)
    --api-key <key>      (o variable de entorno AGW_CLIENT_KEY)


EJEMPLO COMPLETO:
    export AGW_CLIENT_KEY=devkey
    zankora channels --host 127.0.0.1 --port 8787


======================================================================

NOTAS
-----

- zankora-gateway es el SERVIDOR
- zankora es el CLIENTE (control plane)
- Toda operación del CLI usa WebSocket RPC
- El gateway es Single Authority: estado, política y eventos
  viven exclusivamente en el servidor

======================================================================

```


---

## ⚙️ Configuration

```bash
cp .env.example .env
```

Example `.env`:

```env
AGW_HOST=127.0.0.1
AGW_PORT=8787
AGW_INSTANCE_ID=zankora-01

AGW_REQUIRE_CLIENT_AUTH=true
AGW_CLIENT_API_KEYS=["devkey","prodkey"]

AGW_RATE_LIMIT_RPS=10
AGW_RATE_LIMIT_BURST=20

AGW_DATA_DIR=./data
AGW_PLUGIN_DIR=./plugins

AGW_LLM_PROVIDER=mock
AGW_LOG_LEVEL=INFO
AGW_LOG_FORMAT=json
```

---

## ▶️ Running Zankora

```bash
python -m gateway
```

Endpoints:
- **HTTP**: http://127.0.0.1:8787
- **WebSocket**: ws://127.0.0.1:8787/ws
- **Metrics**: /metrics
- **Health**: /healthz

---

## 📡 WebSocket Control Plane

Zankora uses a **request/response + event** protocol over WebSockets.

### Authentication

```json
{
  "type": "req:hello",
  "id": "msg_001",
  "payload": {
    "client_key": "devkey"
  }
}
```

### Core Requests
- `req:channels.list`
- `req:chat.list`
- `req:chat.messages`
- `req:agent.run`
- `req:runs.tail`
- `req:config.get`
- `req:config.set`
- `req:doctor.audit`
- `req:approval.grant`

### Core Events
- `evt:message.inbound`
- `evt:run.progress`
- `evt:run.tool_call`
- `evt:run.output`
- `evt:run.completed`
- `evt:security.blocked`
- `evt:approval.required`

---

## 🔌 Plugin Development

Plugins extend Zankora without modifying core code.

```python
from gateway.plugins.registry import PluginRegistry
from gateway.domain.models import ToolSpec, ToolPermission

def register(registry: PluginRegistry):
    registry.register_tool(
        ToolSpec(
            name="example.echo",
            description="Echo input text",
            permission=ToolPermission.read,
            func=lambda text: {"echo": text},
            parameters={
                "text": {"type": "string"}
            }
        )
    )
```

Plugins are loaded automatically from `AGW_PLUGIN_DIR`.

---

## 🔐 Security Model

- **Deny-by-default** tool execution
- **Rate limits** per channel and user
- **Approval gates** for write tools
- **Audit events** for all security decisions
- **Client API key authentication**

Zankora is designed to be safe to expose to real users.

---

## 📊 Observability

### Metrics
Exposed via Prometheus:
- Agent runs
- Tool calls
- Blocked actions
- Event throughput
- Active connections

### Logging
- Structured JSON logs
- Correlation via `run_id`
- Suitable for ELK / Loki / Cloud logging

### Health Checks

```json
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "event_bus": "ok",
    "channels": "ready"
  }
}
```

---

## 🏭 Deployment

### Docker

```bash
docker build -t zankora:latest .
docker run -p 8787:8787 zankora:latest
```

### Docker Compose

```bash
docker-compose up -d
```

Includes:
- Zankora Gateway
- PostgreSQL
- Prometheus
- Grafana
- Nginx

---

## 🗺️ Roadmap

- Redis-backed event bus
- Horizontal scaling
- Slack & Discord adapters
- Admin dashboard
- Multi-tenant isolation
- Policy-as-code

---
```
======================================================================
                           ZANKORA
                        USE CASES
======================================================================


1) AGENTE MULTICANAL EMPRESARIAL
-------------------------------
Un mismo agente operando de forma consistente en múltiples canales.

CANALES:
    - WebChat
    - Telegram
    - WhatsApp Business

ZANKORA HACE:
    - Normaliza mensajes entrantes
    - Mantiene contexto por chat
    - Aplica políticas por canal/usuario
    - Centraliza estado y decisiones

CASO REAL:
    Un asistente corporativo responde igual en Web y Telegram,
    con reglas de seguridad distintas por canal.


======================================================================


2) AI CON HERRAMIENTAS (TOOL-AUGMENTED LLM)
------------------------------------------
Agentes que ejecutan acciones reales vía tools.

EJEMPLOS DE TOOLS:
    - Consultar bases de datos
    - Crear tickets
    - Ejecutar workflows
    - Llamar APIs internas

ZANKORA HACE:
    - Registro centralizado de tools
    - Allow-list por nombre de tool
    - Bloqueo por defecto
    - Auditoría de cada ejecución

CASO REAL:
    Un agente que consulta datos, pero solo escribe
    cuando la política lo permite.


======================================================================


3) HUMAN-IN-THE-LOOP / APROBACIONES
----------------------------------
Acciones sensibles requieren aprobación humana.

CUANDO SE ACTIVA:
    - Tools de tipo WRITE
    - Operaciones de alto impacto
    - Riesgo regulatorio

ZANKORA HACE:
    - Bloquea ejecución
    - Emite evt:approval.required
    - Espera aprobación vía CLI o UI
    - Reanuda o cancela el run

CASO REAL:
    Un agente quiere borrar datos o enviar un correo externo.
    Un operador debe aprobar explícitamente.


======================================================================


4) CONTROL PLANE DE AGENTES (OPERACIÓN)
--------------------------------------
Operar agentes como sistemas, no como scripts.

OPERACIONES:
    - Listar canales
    - Inspeccionar chats
    - Ejecutar runs manuales
    - Ver eventos en tiempo real
    - Auditar estado del sistema

ZANKORA HACE:
    - WebSocket RPC
    - Eventos server-push
    - Estado observable y reproducible

CASO REAL:
    Un SRE o Tech Lead monitorea y controla agentes
    desde CLI o dashboard.


======================================================================


5) SEGURIDAD Y GOVERNANCE DE IA
-------------------------------
IA bajo reglas claras y auditables.

ZANKORA HACE:
    - Rate limiting por usuario/canal
    - Deny-by-default
    - Logs estructurados
    - Event sourcing de decisiones

CASO REAL:
    Evitar abuso, prompt injection operacional,
    o ejecuciones fuera de política.


======================================================================


6) ORQUESTADOR DE AGENTES (NO SOLO CHAT)
---------------------------------------
Zankora no es un chatbot, es un runtime.

EJEMPLOS:
    - Agentes batch
    - Agentes reactivos a eventos
    - Agentes con múltiples pasos
    - Agentes con retries y timeouts

ZANKORA HACE:
    - Maneja run_id
    - Aplica límites de pasos
    - Maneja fallos y retries
    - Emite progreso incremental

CASO REAL:
    Un agente que ejecuta 10 pasos con tools,
    puede fallar, reintentarse y quedar auditado.


======================================================================


7) PLATAFORMA DE EXPERIMENTACIÓN CONTROLADA
-------------------------------------------
Probar agentes sin romper producción.

ZANKORA HACE:
    - Mock LLM provider
    - Canales aislados
    - Plugins hot-load
    - Configuración dinámica

CASO REAL:
    Probar nuevas tools o prompts en un canal
    sin afectar usuarios reales.


======================================================================


8) BACKEND PARA DASHBOARD / UI
------------------------------
Zankora como backend headless.

CLIENTES:
    - CLI
    - Admin UI
    - Web dashboard
    - Integraciones internas

ZANKORA HACE:
    - API estable vía WebSocket
    - Push de eventos
    - Fuente única de verdad

CASO REAL:
    Un dashboard interno mostrando runs, bloqueos,
    aprobaciones y métricas en tiempo real.


======================================================================


9) CUMPLIMIENTO Y AUDITORÍA
---------------------------
Preparado para entornos regulados.

ZANKORA HACE:
    - Logs inmutables de eventos
    - Trazabilidad por run_id
    - Historial de decisiones
    - Separación control / ejecución

CASO REAL:
    Poder responder:
        "¿Qué hizo este agente?"
        "¿Quién lo aprobó?"
        "¿Con qué datos?"
        "¿Cuándo?"

======================================================================


RESUMEN RÁPIDO
--------------
Zankora sirve cuando necesitas:

    - Agentes en producción (no demos)
    - Control, seguridad y visibilidad
    - Multi-canal real
    - Tooling con gobernanza
    - Human-in-the-loop
    - Observabilidad completa

SI NO NECESITAS ESTO:
    - Un simple chatbot
    - Un script local
    - Un playground de prompts

ENTONCES:
    Zankora probablemente es demasiado.
    Y eso está bien.

======================================================================

```
---
```
======================================================================
                     ZANKORA - HOW TO EXTEND
           Extender el sistema (Plugins, Tools, Canales)
======================================================================

OBJETIVO
--------
Agregar capacidades SIN modificar el core:
  - Nuevas TOOLS (acciones)
  - Nuevos CANALES (adapters)
  - Nuevas INTEGRACIONES (APIs externas)
  - (Opcional) Nuevo MOTOR de agente


======================================================================
1) EXTENDER CON PLUGINS (FORMA RECOMENDADA)
======================================================================

Zankora carga plugins desde:
  AGW_PLUGIN_DIR=./plugins

En startup, el gateway:
  - Escanea directorio
  - Importa módulos Python
  - Ejecuta register(registry)

CONVENCION MINIMA
-----------------
Estructura típica:

  plugins/
    my_plugin/
      __init__.py
      plugin.py

El archivo plugin.py debe exponer:
  def register(registry): ...

NOTA:
  - El core debe permanecer igual.
  - El plugin sólo registra cosas (tools, etc.).


======================================================================
2) AGREGAR UNA TOOL (ACCION) VIA PLUGIN
======================================================================

CASO DE USO
-----------
Quieres que el agente pueda llamar una acción:
  - "crm.search_customer"
  - "tickets.create"
  - "inventory.get_stock"
  - "core.summarize"
  - etc.

PASOS
-----
A) Crear plugin
B) Registrar la tool en register(...)
C) Definir permisos (read/write)
D) (Importante) Permitirla en policy/allowlist

EJEMPLO (PLUGIN TOOL READ)
--------------------------
Archivo: plugins/acme_tools/plugin.py

  - Registra una tool "acme.uppercase"
  - Permiso: READ (no requiere approval)

PSEUDOCODIGO:

  from gateway.plugins.registry import PluginRegistry
  from gateway.domain.models import ToolSpec, ToolPermission

  async def uppercase(text: str) -> dict:
      return {"result": text.upper()}

  def register(registry: PluginRegistry) -> None:
      registry.register_tool(
          ToolSpec(
              name="acme.uppercase",
              description="Convert text to uppercase",
              permission=ToolPermission.read,
              func=uppercase,
              parameters={
                  "text": {"type":"string","description":"Text to convert"}
              }
          )
      )

TOOL WRITE + APPROVAL (RECOMENDADO)
-----------------------------------
Si la tool hace cambios (WRITE):
  - permission = write
  - Zankora puede bloquear hasta aprobación humana

Ejemplo:
  name="tickets.create"
  permission=ToolPermission.write

RESULTADO:
  - Si policy requiere approvals para write tools:
      evt:approval.required
  - Luego operador aprueba:
      zankora approve <run_id>


======================================================================
3) HABILITAR LA TOOL (POLICY / ALLOWLIST)
======================================================================

POR QUE
-------
Zankora es deny-by-default: una tool nueva NO debería ejecutarse
si no está explicitamente permitida.

QUE HACER
---------
A) Permitir tool por configuración dinámica (si existe config-set)
B) O agregarla al archivo de policy/config en el core (según diseño)

EJEMPLO LOGICO
--------------
Permitir:
  - acme.uppercase = true

Y para write:
  - tickets.create = true
  - approvals requeridas = true

CHECKLIST DE SEGURIDAD
----------------------
[ ] Tool con nombre namespace claro (company.feature.action)
[ ] Permisos correctos (read vs write)
[ ] Validación de parámetros (tipos, largo, defaults)
[ ] Sanitización de outputs (no filtrar secretos)
[ ] Manejo de errores (no reventar el loop principal)
[ ] Observabilidad: log + eventos relevantes


======================================================================
4) EXTENDER CON UN NUEVO CANAL (ADAPTER)
======================================================================

CASO DE USO
-----------
Quieres integrar un canal nuevo:
  - Slack
  - Discord
  - Email
  - MS Teams
  - Webhook genérico

PATRON
------
Un canal en Zankora es un adapter que:
  - Recibe mensajes externos
  - Normaliza a evento inbound
  - Envía outbound (respuestas) al canal

DONDE MIRAR
-----------
  gateway/channels/base.py          (contrato)
  gateway/channels/webchat.py       (ejemplo simple)
  gateway/channels/telegram.py      (ejemplo real)
  gateway/channels/whatsapp_business.py (skeleton)

FORMA 1 (SIMPLE)
----------------
A) Implementar un ChannelAdapter nuevo en gateway/channels/
B) Agregarlo al ensure_channel(...) en core/gateway.py

FORMA 2 (MEJOR PARA ESCALAR)
----------------------------
A) Hacerlo como plugin:
   - plugin registra el canal
   - core lo descubre y lo instancia

NOTA:
Si hoy el core solo crea canales "hardcoded" con _ensure_channel,
la extensión real por plugin requiere un hook para registrar canales.
(Se puede agregar sin romper el core, pero hay que definir el contrato.)

CHECKLIST CANAL
---------------
[ ] Identificador estable (ej: slack-1)
[ ] start() / stop() con shutdown limpio
[ ] reconexión si aplica
[ ] rate limit (por user/canal)
[ ] autenticación del canal (signatures, tokens)
[ ] normalización inbound:
     chat_id, sender_id, text, msg_id, ts
[ ] envío outbound: send(chat_id, text, metadata)


======================================================================
5) AGREGAR INTEGRACIONES (APIs EXTERNAS)
======================================================================

CASO DE USO
-----------
Quieres que tools hablen con:
  - CRM
  - ERP
  - DB corporativa
  - APIs internas

RECOMENDACION
-------------
Implementar integración como:
  - Cliente Python aislado (acme_clients/)
  - Usado por tools registradas en plugins

GOOD PRACTICES
--------------
- Timeouts estrictos
- Retries (solo idempotentes)
- Circuit breaker (si falla externo)
- Logs con run_id
- No exponer secretos en logs/eventos


======================================================================
6) EXTENDER EL MOTOR DE AGENTE (OPCIONAL)
======================================================================

CASO DE USO
-----------
Quieres cambiar el runtime:
  - Simple runner -> LangGraph engine
  - o motor propio (planner/reflector/etc.)

DONDE MIRAR
-----------
  gateway/agent/engine.py
  gateway/agent/runner.py
  gateway/agent/langgraph_engine.py
  LANGGRAPH_IMPLEMENTATION.md

PATRON
------
- Implementas una clase Engine que:
  - recibe contexto + prompt
  - ejecuta pasos
  - emite eventos (progress/tool_call/output)
  - respeta max_steps y timeout
- Activación por config:
  AGW_AGENT_ENGINE=simple|langgraph|custom


======================================================================
7) EXTENSION: EVENTOS Y AUDITORIA
======================================================================

OBJETIVO
--------
Que cada extensión sea observable y auditable.

REGLA
-----
Cuando algo ocurra:
  - tool call
  - tool result
  - bloqueo por policy
  - approval requerido
  - excepción externa

Debe:
  - Emitir evento
  - Registrar log estructurado
  - Incluir run_id y channel_id


======================================================================
8) PLANTILLA RAPIDA (PLUGIN LISTO)
======================================================================

Estructura:

  plugins/my_plugin/
    plugin.py

Contenido mínimo (conceptual):

  def register(registry):
      registry.register_tool(...)

Deploy:
  - Copias carpeta a AGW_PLUGIN_DIR
  - Reinicias zankora-gateway
  - Verificas:
      zankora doctor
      zankora channels
      zankora run <chat> --prompt "..."

======================================================================

```
---
---

## 📄 License

MIT License

---

<div align="center">

**Zankora — Control your agents. Trust their behavior.**

**Author: Juan Carlos Lanas Ocampo**

</div>
<div align="center">  
Zankora es llamada.

Zankora nace cuando muchos caminos se cruzan
y uno solo debe guiar.

Es la voz que ordena al tambor,
la mano que conoce el ritmo antes del golpe.

En lengua antigua, Zankora es:
“Aquel que abre paso para que otros hablen”
Zankora camina delante del mensaje,
escucha antes de responder,
y no habla dos veces lo mismo.

**Zankora escucha el mensaje entrante, lo normaliza, lo pasa por la ley (políticas), convoca herramientas bajo permiso, y canta la historia completa en eventos, logs y métricas.**
</div>
