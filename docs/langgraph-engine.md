# LangGraph Agent Engine

## Overview

The Agent Gateway supports two execution engines:

1. **Simple Engine** (default) - Original MVP implementation with linear flow
2. **LangGraph Engine** - Advanced state graph-based orchestration with structured workflows

The LangGraph engine provides better control flow, clearer state management, and easier debugging while maintaining the same security guarantees and single-authority principle.

## Installation

LangGraph is an optional dependency. To enable it:

```bash
# Install with LangGraph support
pip install -e .[agentic]

# Or install all optional dependencies
pip install -e .[all]
```

## Configuration

### Environment Variable

Set the agent engine in your `.env` file:

```env
AGW_AGENT_ENGINE=langgraph
```

Or use the default simple engine:

```env
AGW_AGENT_ENGINE=simple
```

### Programmatic Configuration

```python
from gateway.config import Settings

settings = Settings(agent_engine="langgraph")
```

## Architecture

### State Graph Structure

The LangGraph engine uses a state machine with the following nodes:

```
┌─────────────────┐
│ build_context   │ ← Entry point
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│      plan       │ ← LLM decides action
└────────┬────────┘
         │
         ▼
    [Tool request?]
         │
    ┌────┴─────┐
    │          │
    ▼          ▼
┌────────┐  ┌────────────┐
│ policy │  │decide_next │
│ check  │  └────────────┘
└────┬───┘
     │
[Needs approval?]
     │
  ┌──┴───┐
  │      │
  ▼      ▼
┌──────┐ ┌────────┐
│wait  │ │execute │
│appr. │ │  tool  │
└──┬───┘ └───┬────┘
   │         │
   └────┬────┘
        │
        ▼
  ┌────────────┐
  │decide_next │
  └─────┬──────┘
        │
   [Done?]
        │
     ┌──┴──┐
     │     │
     ▼     ▼
  ┌───────┐ ┌──────────┐
  │finish │ │ask_clar. │
  └───────┘ └──────────┘
```

### State Schema

```python
class GraphState(TypedDict):
    run_id: str              # Run identifier
    chat_id: str             # Chat context
    channel_id: str          # Channel identifier
    requested_by: str        # User who requested
    messages: list           # Conversation history
    step: int                # Current step number
    plan: str | None         # LLM's plan/decision
    tool_request: dict | None  # Pending tool call
    tool_result: dict | None   # Last tool result
    output_chunks: list[str]   # Accumulated output
    needs_approval: bool       # Approval flag
    blocked_reason: str | None # Block reason if any
    done: bool                 # Completion flag
    max_steps: int             # Step limit
    timeout_s: int             # Timeout limit
```

## Nodes Description

### 1. build_context
- **Purpose**: Initialize context and prepare for execution
- **Events**: `evt:run.progress` with phase start/end
- **Transitions**: Always to `plan`

### 2. plan
- **Purpose**: Call LLM to decide next action (tool call or output)
- **Events**: `evt:run.progress`
- **Transitions**: 
  - If tool_request → `policy_check`
  - Otherwise → `decide_next`

### 3. policy_check
- **Purpose**: Validate tool permissions via PolicyEngine
- **Events**: `evt:run.progress`, `evt:security.blocked` if denied
- **Transitions**:
  - If needs_approval → `wait_approval`
  - If blocked → `decide_next`
  - Otherwise → `execute_tool`

### 4. wait_approval
- **Purpose**: Wait for human approval with timeout
- **Events**: `evt:run.tool_call` (approval_required=true), `evt:security.blocked` on timeout
- **Transitions**: 
  - If approved → `execute_tool`
  - If timeout → sets done=true (via decide_next logic)

### 5. execute_tool
- **Purpose**: Execute approved tool via ToolRegistry
- **Events**: `evt:run.tool_call` (approval_required=false), `evt:run.progress` with result
- **Transitions**: Always to `decide_next`

### 6. decide_next
- **Purpose**: Determine if run is complete or should continue
- **Logic**:
  - Has output → done=true
  - Blocked without output → trigger ask_clarification
  - Max steps reached → done=true
  - Otherwise → increment step, continue to plan
- **Transitions**:
  - If done → `finalize`
  - If blocked without output → `ask_clarification`
  - Otherwise → `plan`

### 7. ask_clarification
- **Purpose**: Fallback when blocked without output
- **Events**: `evt:run.output` with clarification message
- **Transitions**: Always to `finalize`

### 8. finalize
- **Purpose**: Cleanup and prepare final state
- **Events**: `evt:run.progress`
- **Transitions**: To END

## Event Flow Example

### Scenario: Tool Call with Approval

```
User: "Send an email to john@example.com saying hello"
```

**Events emitted:**

```json
// 1. Run started
{
  "type": "evt:run.progress",
  "payload": {
    "status": "started",
    "engine": "langgraph"
  }
}

// 2. Context built
{
  "type": "evt:run.progress",
  "payload": {
    "node": "build_context",
    "phase": "start",
    "step": 1
  }
}

// 3. Planning
{
  "type": "evt:run.progress",
  "payload": {
    "node": "plan",
    "phase": "end",
    "step": 1,
    "plan": "Tool requested: email.send"
  }
}

// 4. Policy check
{
  "type": "evt:run.progress",
  "payload": {
    "node": "policy_check",
    "phase": "end",
    "step": 1,
    "allowed": true,
    "needs_approval": true
  }
}

// 5. Approval required
{
  "type": "evt:run.tool_call",
  "payload": {
    "tool": "email.send",
    "args": {"to": "john@example.com", "body": "hello"},
    "approval_required": true
  }
}

// 6. Waiting for approval
{
  "type": "evt:run.progress",
  "payload": {
    "node": "wait_approval",
    "phase": "waiting",
    "step": 1
  }
}

// ... User grants approval via req:approval.grant ...

// 7. Tool execution
{
  "type": "evt:run.tool_call",
  "payload": {
    "tool": "email.send",
    "args": {"to": "john@example.com", "body": "hello"},
    "approval_required": false
  }
}

// 8. Tool result
{
  "type": "evt:run.progress",
  "payload": {
    "node": "execute_tool",
    "phase": "result",
    "step": 1,
    "tool": "email.send"
  }
}

// 9. Next planning iteration (step 2)
{
  "type": "evt:run.progress",
  "payload": {
    "node": "plan",
    "phase": "end",
    "step": 2,
    "plan": "Email sent successfully"
  }
}

// 10. Final output
{
  "type": "evt:run.output",
  "payload": {
    "text": "Email sent successfully to john@example.com"
  }
}

// 11. Finalize
{
  "type": "evt:run.progress",
  "payload": {
    "node": "finalize",
    "phase": "start",
    "step": 2
  }
}

// 12. Completed (emitted by Gateway)
{
  "type": "evt:run.completed",
  "payload": {
    "status": "completed",
    "summary": "Completed successfully"
  }
}
```

## Granting Approvals

Approvals work the same way regardless of engine:

### Via WebSocket

```json
{
  "type": "req:approval.grant",
  "id": "msg_123",
  "ts": "2026-01-30T20:00:00.000Z",
  "payload": {
    "run_id": "run_abc123"
  }
}
```

### Via CLI

```bash
agw approve run_abc123
```

## Comparison: Simple vs LangGraph

| Feature | Simple Engine | LangGraph Engine |
|---------|---------------|------------------|
| Control Flow | Linear loop | State graph |
| State Management | Local variables | Typed state dict |
| Debugging | Print/logs | Graph visualization |
| Extensibility | Modify loop | Add/modify nodes |
| Fallback Handling | Implicit | Explicit ask_clarification node |
| Testing | Mock LLM calls | Mock + state inspection |
| Performance | Slightly faster | More overhead |
| Dependencies | None | LangGraph + langchain-core |

## When to Use LangGraph Engine

**Use LangGraph when:**
- You need complex multi-step workflows
- You want clear state visualization
- You need better debugging/observability
- You plan to extend with custom nodes
- You need explicit fallback handling

**Use Simple Engine when:**
- You want minimal dependencies
- Performance is critical
- Workflows are straightforward
- You prefer simpler code

## Fallback Behavior

When the LangGraph engine encounters issues, it provides clear fallbacks:

### Tool Not Found
```
Output: "I encountered an issue (tool_missing) and couldn't complete the task. 
Could you provide more information or rephrase your request?"
```

### Policy Denied
```
Output: "I encountered an issue (policy_denied) and couldn't complete the task. 
Could you provide more information or rephrase your request?"
```

### Approval Timeout
```
Status: failed
Summary: "Approval timeout"
```

## Observability

All LangGraph runs include:
- `run_id` in every log entry (via `bind_run_id`)
- Node name in progress events
- Phase indicators (start/end/waiting/result)
- Step counter
- Tool execution details

### Log Example

```json
{
  "timestamp": "2026-01-30T20:00:00.000Z",
  "level": "INFO",
  "logger": "langgraph_engine",
  "message": "plan_tool",
  "run_id": "run_abc123",
  "tool": "email.send"
}
```

## Troubleshooting

### Error: "LangGraph engine requested but not available"

**Cause**: LangGraph not installed

**Solution**:
```bash
pip install -e .[agentic]
```

### Error: "Max recursion depth exceeded"

**Cause**: Infinite loop in graph (shouldn't happen with current design)

**Solution**: Check max_steps configuration and graph logic

### Warning: "LangGraph not installed"

**Cause**: Trying to import LangGraphEngine without installation

**Solution**: Either install LangGraph or use simple engine

## Best Practices

1. **Always set max_steps**: Prevents infinite loops
   ```env
   AGW_RUN_MAX_STEPS=20
   ```

2. **Configure appropriate timeouts**: For long-running tools
   ```env
   AGW_RUN_TIMEOUT_S=300
   ```

3. **Enable approval workflows in production**:
   ```env
   AGW_REQUIRE_APPROVALS_FOR_WRITE_TOOLS=true
   ```

4. **Monitor progress events**: Subscribe to progress events for real-time tracking

5. **Use run_id for debugging**: All logs include run_id for tracing

## Migration from Simple to LangGraph

No code changes needed! Just:

1. Install dependencies: `pip install -e .[agentic]`
2. Set environment variable: `AGW_AGENT_ENGINE=langgraph`
3. Restart gateway: `python -m gateway`

All existing tools, policies, and configurations work identically.

## Advanced: Custom Nodes

You can extend LangGraphEngine by subclassing and adding custom nodes:

```python
class CustomLangGraphEngine(LangGraphEngine):
    def _build_graph(self):
        workflow = super()._build_graph()
        
        # Add custom node
        workflow.add_node("custom_validation", self._custom_validation)
        
        # Modify edges
        # ... your custom logic ...
        
        return workflow.compile()
    
    async def _custom_validation(self, state):
        # Your custom logic
        return state
```

## Support

For issues or questions:
- Check logs with `AGW_LOG_LEVEL=DEBUG`
- Review event stream for state transitions
- Consult source: `gateway/agent/langgraph_engine.py`
