# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-01-30

### Added
- **Circuit Breaker Pattern**: Protection against cascading failures with configurable thresholds
- **Advanced Retry Logic**: Exponential backoff with tenacity for transient failures
- **Enhanced Observability**: Comprehensive Prometheus metrics and structured logging
- **Production Deployment Guide**: Complete documentation for production deployments
- **Plugin System Enhancements**: Hot-reload support and better error handling
- **Additional Example Plugins**:
  - Web search plugin with URL fetching
  - Mathematical calculations plugin with statistics
- **Docker Compose Stack**: Full production stack with PostgreSQL, Redis, Prometheus, and Grafana
- **Kubernetes Manifests**: Production-ready K8s deployment configurations
- **Security Enhancements**:
  - Approval workflow system for sensitive operations
  - Enhanced rate limiting with token bucket algorithm
  - Input sanitization and validation
- **Development Tools**:
  - Makefile for common development tasks
  - Comprehensive test suite with pytest
  - Code quality tools (Black, Ruff, mypy)
- **Documentation**:
  - Plugin development guide
  - Deployment best practices
  - Security hardening guide
  - Contributing guidelines

### Changed
- **Configuration System**: Migrated to Pydantic Settings for better validation
- **Database Layer**: Improved async SQLAlchemy usage with better error handling
- **Event Bus**: Best-effort delivery with configurable queue sizes
- **WebSocket Protocol**: Enhanced error handling and reconnection logic
- **CLI**: Improved commands with Rich formatting and better UX

### Fixed
- Memory leaks in event bus subscribers
- Race conditions in agent runner
- WebSocket connection stability issues
- Database connection pool exhaustion

### Security
- Added support for secrets management (AWS Secrets Manager, Vault)
- Implemented proper SSL/TLS configuration in Nginx
- Enhanced input validation and sanitization
- Added security audit tooling (pip-audit, bandit)

## [0.1.0] - 2025-11-01

### Added
- Initial release with core functionality
- Multi-channel support (Telegram, WhatsApp, WebChat)
- WebSocket-based RPC protocol
- Plugin system for extensibility
- SQLite persistence layer
- Basic security features (API keys, allowlists)
- Agent runner with LLM integration
- Event bus for real-time updates
- CLI for operations
- Basic observability (logs, metrics)

### Core Features
- Single authority design pattern
- Async/await throughout
- Type-safe with Pydantic models
- Production-ready error handling
- Health checks and graceful shutdown

[0.2.0]: https://github.com/agent-gateway/agent-gateway/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/agent-gateway/agent-gateway/releases/tag/v0.1.0
