# Plugin Development Guide

This guide explains how to create custom plugins for the Agent Gateway to extend its functionality with new tools, commands, and channel integrations.

## Overview

Plugins are self-contained modules that can add:
- **Tools**: Functions that agents can call to perform actions
- **Commands**: CLI commands for operators
- **Channels**: New communication channel adapters
- **Hooks**: Lifecycle hooks for custom logic

## Plugin Structure

```
plugins/
└── my_plugin/
    ├── plugin.py          # Required: Plugin entry point
    ├── __init__.py        # Optional: Package initialization
    ├── helpers.py         # Optional: Helper functions
    ├── config.json        # Optional: Plugin configuration
    └── README.md          # Optional: Plugin documentation
```

## Basic Plugin Template

```python
"""My custom plugin."""
from __future__ import annotations

from gateway.domain.models import ToolPermission, ToolSpec
from gateway.plugins.registry import PluginRegistry


def my_tool_function(param1: str, param2: int = 10) -> dict:
    """
    Description of what this tool does.
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter
        
    Returns:
        Result dictionary
    """
    # Your implementation here
    result = f"Processed: {param1} with {param2}"
    
    return {
        "success": True,
        "result": result,
        "metadata": {"param1": param1, "param2": param2}
    }


def register(registry: PluginRegistry) -> None:
    """
    Register plugin components.
    
    This function is called when the plugin is loaded.
    """
    # Register your tool
    registry.register_tool(
        ToolSpec(
            name="my_plugin.my_tool",
            description="Clear description for the LLM to understand when to use this tool",
            permission=ToolPermission.read,  # or ToolPermission.write
            func=my_tool_function,
            parameters={
                "param1": {
                    "type": "string",
                    "description": "What param1 represents",
                },
                "param2": {
                    "type": "integer",
                    "description": "What param2 represents",
                    "default": 10,
                },
            },
        )
    )
    
    print("✅ My plugin loaded successfully")
```

## Tool Permissions

### READ Permission
Tools with `ToolPermission.read` can be called without approval:
- Read data from external APIs
- Perform calculations
- Search and retrieve information
- Generate responses

### WRITE Permission
Tools with `ToolPermission.write` require human approval (if enabled):
- Modify external resources
- Send emails or messages
- Create or delete records
- Financial transactions

Example:
```python
registry.register_tool(
    ToolSpec(
        name="email.send",
        description="Send an email to a recipient",
        permission=ToolPermission.write,  # Requires approval
        func=send_email_function,
        parameters={
            "to": {"type": "string", "description": "Recipient email"},
            "subject": {"type": "string", "description": "Email subject"},
            "body": {"type": "string", "description": "Email body"},
        },
    )
)
```

## Async Tools

For I/O-bound operations, use async functions:

```python
import httpx

async def fetch_data(url: str) -> dict:
    """Fetch data from an API asynchronously."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return {
            "url": url,
            "status": response.status_code,
            "data": response.json(),
        }

def register(registry: PluginRegistry) -> None:
    registry.register_tool(
        ToolSpec(
            name="api.fetch",
            description="Fetch data from a URL",
            permission=ToolPermission.read,
            func=fetch_data,  # Async function
            parameters={
                "url": {"type": "string", "description": "URL to fetch"},
            },
        )
    )
```

## Error Handling

Always handle errors gracefully:

```python
def robust_tool(input_data: str) -> dict:
    """Tool with proper error handling."""
    try:
        # Your logic here
        result = process_data(input_data)
        
        return {
            "success": True,
            "result": result,
        }
        
    except ValueError as e:
        # Validation error
        return {
            "success": False,
            "error": f"Invalid input: {e}",
            "error_type": "validation",
        }
        
    except Exception as e:
        # Unexpected error
        return {
            "success": False,
            "error": f"Operation failed: {e}",
            "error_type": "unknown",
        }
```

## Parameter Schemas

Define clear parameter schemas for LLM understanding:

```python
parameters={
    "text": {
        "type": "string",
        "description": "Text to process",
        "minLength": 1,
        "maxLength": 1000,
    },
    "mode": {
        "type": "string",
        "description": "Processing mode",
        "enum": ["fast", "accurate", "balanced"],
        "default": "balanced",
    },
    "options": {
        "type": "object",
        "description": "Additional options",
        "properties": {
            "uppercase": {"type": "boolean", "default": False},
            "trim": {"type": "boolean", "default": True},
        },
    },
    "tags": {
        "type": "array",
        "description": "List of tags",
        "items": {"type": "string"},
    },
}
```

## Logging

Use structured logging in your plugins:

```python
from gateway.observability.logging import get_logger

log = get_logger("my_plugin")

def my_tool(param: str) -> dict:
    log.info("tool_called", param=param)
    
    try:
        result = process(param)
        log.debug("processing_complete", result_length=len(result))
        return {"result": result}
        
    except Exception as e:
        log.error("tool_error", error=str(e), param=param)
        raise
```

## Testing Plugins

Create tests for your plugins:

```python
# tests/test_my_plugin.py
import pytest
from plugins.my_plugin.plugin import my_tool_function

def test_my_tool_success():
    result = my_tool_function("test", 5)
    assert result["success"] is True
    assert "test" in result["result"]

def test_my_tool_defaults():
    result = my_tool_function("test")
    assert result["metadata"]["param2"] == 10

@pytest.mark.asyncio
async def test_async_tool():
    from plugins.my_plugin.plugin import my_async_tool
    result = await my_async_tool("input")
    assert "result" in result
```

## Plugin Configuration

Add a `config.json` for plugin settings:

```json
{
  "name": "my_plugin",
  "version": "1.0.0",
  "description": "My custom plugin for the gateway",
  "author": "Your Name",
  "settings": {
    "api_key": "${MY_PLUGIN_API_KEY}",
    "timeout": 30,
    "max_retries": 3
  },
  "dependencies": [
    "httpx>=0.26.0",
    "beautifulsoup4>=4.12.0"
  ]
}
```

Load config in your plugin:

```python
import json
import os

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path) as f:
        config = json.load(f)
    
    # Replace env variables
    api_key = os.getenv("MY_PLUGIN_API_KEY", config["settings"]["api_key"])
    return config, api_key
```

## Best Practices

1. **Naming**: Use descriptive names in format `plugin_name.tool_name`
2. **Documentation**: Write clear docstrings and parameter descriptions
3. **Error Handling**: Return structured error information
4. **Security**: Validate and sanitize all inputs
5. **Performance**: Use async for I/O operations
6. **Logging**: Log important events for debugging
7. **Testing**: Write tests for all tools
8. **Dependencies**: Minimize external dependencies

## Example Plugins

Check these example plugins in the `plugins/` directory:

- `sample_echo/` - Simple text transformation
- `web_search/` - Web search and URL fetching
- `math_tools/` - Mathematical calculations
- `file_ops/` - File system operations (write permission)

## Plugin Loading

Plugins are automatically loaded at gateway startup from the `AGW_PLUGIN_DIR` directory (default: `./plugins`).

To manually reload plugins (if hot-reload is enabled):
```bash
agw reload-plugins
```

## Debugging

Enable debug logging to see plugin loading details:
```bash
export AGW_LOG_LEVEL=DEBUG
python -m gateway
```

## Publishing Plugins

To share your plugin with others:

1. Create a Git repository
2. Add clear README with installation instructions
3. List all dependencies in `requirements.txt`
4. Include example usage
5. Add tests
6. Tag releases with semantic versioning

## Support

For plugin development questions:
- Check the examples in `plugins/`
- Review the codebase in `gateway/plugins/`
- Open an issue on GitHub
