# Protocolo WebSocket (RPC + Event Stream)

## Mensaje base
```json
{
  "type": "req:channels.list",
  "id": "c1b2...",
  "ts": "2026-01-30T16:00:00.000Z",
  "payload": {}
}
```

- `type`: `req:*` (requests), `res:*` (responses), `evt:*` (server push)
- `id`: correlación request/response; para eventos el server usa `evt_<seq>`
- `ts`: ISO-8601 UTC
- `payload`: dict

## Requests / Responses

### req:hello
Request:
```json
{ "type":"req:hello","id":"1","ts":"...","payload":{} }
```
Response:
```json
{ "type":"res:hello","id":"1","ts":"...","ok":true,
  "payload":{"server":"agent-gateway","version":"0.1.0","instance_id":"agw-1","features":["rpc_ws","event_stream"]}}
```

### req:channels.list
```json
{ "type":"req:channels.list","id":"2","ts":"...","payload":{} }
```
```json
{ "type":"res:channels.list","id":"2","ts":"...","ok":true,
  "payload":{"channels":[{"id":"webchat-1","type":"webchat","status":"online","last_seen":"..."}]}}
```

### req:chat.list
```json
{ "type":"req:chat.list","id":"3","ts":"...","payload":{"channel_id":"webchat-1"} }
```

### req:chat.messages
```json
{ "type":"req:chat.messages","id":"4","ts":"...","payload":{"chat_id":"chat_demo_1","limit":50} }
```

### req:agent.run
```json
{ "type":"req:agent.run","id":"5","ts":"...","payload":{"chat_id":"chat_demo_1","channel_id":"webchat-1","requested_by":"cli","prompt":"hola"} }
```

### req:runs.tail
```json
{ "type":"req:runs.tail","id":"6","ts":"...","payload":{"run_id":"run_abcd","after_seq":120} }
```

### req:config.get / req:config.set
`config.get` devuelve `policy` y `tools`.
`config.set` permite mutar allowlist/tool_allow/dm_policy/group_policy (MVP).

### req:doctor.audit
Devuelve findings y sugerencias.

### req:approval.grant
```json
{ "type":"req:approval.grant","id":"7","ts":"...","payload":{"run_id":"run_abcd"} }
```

## Server Push Events

### evt:channel.status
```json
{ "type":"evt:channel.status","id":"evt_10","ts":"...","payload":{"seq":10,"channel_id":"webchat-1","status":"online"} }
```

### evt:message.inbound
```json
{ "type":"evt:message.inbound","id":"evt_11","ts":"...","payload":{"seq":11,"message":{...}} }
```

### evt:run.progress
```json
{ "type":"evt:run.progress","id":"evt_12","ts":"...","payload":{"run_id":"run_abcd","seq":12,"step":1,"status":"planning"} }
```

### evt:run.tool_call
```json
{ "type":"evt:run.tool_call","id":"evt_13","ts":"...","payload":{"run_id":"run_abcd","seq":13,"tool":"sample.upper","args":{"text":"hi"},"approval_required":false} }
```

### evt:run.output
```json
{ "type":"evt:run.output","id":"evt_14","ts":"...","payload":{"run_id":"run_abcd","seq":14,"text":"MockLLM: recibí: hola"} }
```

### evt:run.completed
```json
{ "type":"evt:run.completed","id":"evt_15","ts":"...","payload":{"run_id":"run_abcd","seq":15,"status":"completed","summary":"Completed","output_text":"..."} }
```

### evt:security.blocked
```json
{ "type":"evt:security.blocked","id":"evt_16","ts":"...","payload":{"seq":16,"reason":"sender_not_allowlisted","channel_id":"webchat-1","sender_id":"u1"} }
```
