# LangGraph Integration - Quick Start

## What is This?

The Agent Gateway now supports **two execution engines**:

1. **Simple Engine** (default) - Linear flow, minimal dependencies
2. **LangGraph Engine** - State graph-based, better observability

## Installation

```bash
# Install LangGraph support
pip install -e .[agentic]
```

## Enable LangGraph

**Option 1: Environment Variable**
```bash
export AGW_AGENT_ENGINE=langgraph
python -m gateway
```

**Option 2: .env File**
```env
AGW_AGENT_ENGINE=langgraph
```

## Key Benefits

✅ **Structured Workflows** - Clear state graph vs linear loop  
✅ **Better Debugging** - Track state transitions through nodes  
✅ **Explicit Fallbacks** - `ask_clarification` node for blocked states  
✅ **Same Security** - All tools go through PolicyEngine + approvals  
✅ **No Breaking Changes** - Drop-in replacement  

## Event Flow Example

```
build_context → plan → policy_check → execute_tool → decide_next → finalize
```

With security:
```
plan → policy_check → wait_approval → execute_tool → decide_next
```

## Example Events

```json
{"type": "evt:run.progress", "payload": {"node": "plan", "step": 1}}
{"type": "evt:run.tool_call", "payload": {"tool": "email.send", "approval_required": true}}
{"type": "evt:run.progress", "payload": {"node": "wait_approval", "phase": "waiting"}}
{"type": "evt:run.progress", "payload": {"node": "execute_tool", "phase": "result"}}
{"type": "evt:run.output", "payload": {"text": "Email sent successfully"}}
```

## Comparison

| Feature | Simple | LangGraph |
|---------|--------|-----------|
| Dependencies | None | +2 packages |
| Flow | Linear loop | State graph |
| Debugging | Logs only | Graph + logs |
| Extensibility | Modify loop | Add nodes |

## Documentation

- **Full Guide**: [docs/langgraph-engine.md](../docs/langgraph-engine.md)
- **Examples**: [examples/langgraph_example.py](langgraph_example.py)
- **Tests**: [tests/test_langgraph_engine.py](../tests/test_langgraph_engine.py)

## Test It

```bash
# Run example
cd examples
python langgraph_example.py

# Run tests
pytest tests/test_langgraph_engine.py -v
```

## Architecture Compliance

✅ **Single Authority Principle**: Gateway owns all state  
✅ **Tool Execution**: Via ToolRegistry + PolicyEngine only  
✅ **Event Bus**: All side effects emit events  
✅ **Approvals**: Same workflow as simple engine  
✅ **No Breaking Changes**: Existing code unchanged  

## When to Use

**Use LangGraph if:**
- You need complex multi-step workflows
- You want better observability
- You plan to customize workflow logic

**Use Simple if:**
- You prefer minimal dependencies
- Performance is critical
- Workflows are straightforward

## Support

Issues? Check:
1. LangGraph installed: `pip show langgraph`
2. Config set: `AGW_AGENT_ENGINE=langgraph`
3. Logs: `AGW_LOG_LEVEL=DEBUG python -m gateway`
