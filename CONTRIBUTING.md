# Contributing to Agent Gateway

Thank you for your interest in contributing to Agent Gateway! This document provides guidelines for contributions.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors.

## How to Contribute

### Reporting Issues

Before creating an issue:
1. Check if the issue already exists
2. Use the issue template
3. Provide clear reproduction steps
4. Include version information

### Suggesting Features

1. Open an issue with the "feature request" label
2. Describe the use case clearly
3. Explain why this would be valuable
4. Consider implementation complexity

### Submitting Pull Requests

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/agent-gateway.git
   cd agent-gateway
   ```

2. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Set Up Development Environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .[dev]
   ```

4. **Make Your Changes**
   - Write clear, documented code
   - Follow existing code style
   - Add tests for new features
   - Update documentation

5. **Run Tests**
   ```bash
   pytest
   black gateway/ tests/
   ruff check gateway/ tests/
   mypy gateway/
   ```

6. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add amazing feature"
   ```
   
   Follow conventional commits:
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation only
   - `style:` - Code style changes
   - `refactor:` - Code refactoring
   - `test:` - Adding tests
   - `chore:` - Maintenance tasks

7. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   
   Then create a Pull Request on GitHub.

## Development Guidelines

### Code Style

- **Python**: Follow PEP 8, use Black for formatting
- **Type Hints**: Use type annotations
- **Docstrings**: Use Google-style docstrings
- **Line Length**: 120 characters max

Example:
```python
async def process_message(
    message: Message,
    config: dict[str, Any],
) -> ProcessedMessage:
    """
    Process an inbound message.
    
    Args:
        message: The message to process
        config: Processing configuration
        
    Returns:
        Processed message with metadata
        
    Raises:
        ValidationError: If message is invalid
    """
    # Implementation
    pass
```

### Testing

- **Coverage**: Aim for >80% code coverage
- **Unit Tests**: Test individual components
- **Integration Tests**: Test component interactions
- **Async Tests**: Use `pytest-asyncio`

Example:
```python
import pytest
from gateway.core.gateway import Gateway

@pytest.mark.asyncio
async def test_message_processing():
    gateway = Gateway(settings, engine, session_factory)
    await gateway.start()
    
    # Test logic
    result = await gateway.process_message(message)
    
    assert result.status == "success"
    await gateway.stop()
```

### Documentation

- Update README.md for major changes
- Add docstrings to all public functions
- Update relevant documentation in `docs/`
- Include examples for new features

### Logging

Use structured logging:
```python
from gateway.observability.logging import get_logger

log = get_logger(__name__)

log.info("event_occurred", user_id=user.id, action="login")
log.error("operation_failed", error=str(e), context=ctx)
```

## Plugin Contributions

To contribute a plugin:

1. Create plugin directory: `plugins/your_plugin/`
2. Implement `plugin.py` with `register()` function
3. Add tests in `tests/test_your_plugin.py`
4. Document in `plugins/your_plugin/README.md`
5. Update main README to list the plugin

See [Plugin Development Guide](docs/plugin-development.md) for details.

## Project Structure

```
agent-gateway/
├── gateway/              # Main application code
│   ├── core/            # Core gateway logic
│   ├── agent/           # Agent runner
│   ├── channels/        # Channel adapters
│   ├── tools/           # Tool registry
│   ├── plugins/         # Plugin system
│   ├── security/        # Security components
│   ├── observability/   # Logging, metrics
│   └── server/          # WebSocket server
├── plugins/             # Plugin implementations
├── tests/               # Test suite
├── docs/                # Documentation
└── webchat/             # WebChat client
```

## Review Process

Pull requests are reviewed for:

1. **Code Quality**: Clean, readable, maintainable
2. **Tests**: Adequate coverage, passing CI
3. **Documentation**: Clear explanations
4. **Security**: No vulnerabilities introduced
5. **Performance**: No significant regressions

Reviewers may request changes. Please respond promptly and iterate.

## Release Process

Releases follow semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Create an Issue
- **Chat**: Join our community chat (if available)

## Recognition

Contributors are recognized in:
- Git history and PR comments
- Release notes
- CONTRIBUTORS.md file

Thank you for contributing to Agent Gateway! 🚀
