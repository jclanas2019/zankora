.PHONY: help install dev-install test lint format clean run docker-build docker-run docs

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install production dependencies
	pip install -e .

dev-install: ## Install development dependencies
	pip install -e .[dev]

install-all: ## Install all optional dependencies
	pip install -e .[all]

test: ## Run tests
	pytest -v

test-cov: ## Run tests with coverage
	pytest --cov=gateway --cov-report=html --cov-report=term

test-fast: ## Run tests without slow tests
	pytest -v -m "not slow"

lint: ## Run linters
	ruff check gateway/ tests/
	mypy gateway/

format: ## Format code
	black gateway/ tests/ plugins/
	ruff check --fix gateway/ tests/

format-check: ## Check code formatting
	black --check gateway/ tests/ plugins/

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf htmlcov
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

run: ## Run the gateway locally
	python -m gateway

run-dev: ## Run the gateway in development mode
	AGW_REQUIRE_CLIENT_AUTH=false AGW_LOG_LEVEL=DEBUG python -m gateway

docker-build: ## Build Docker image
	docker build -t agent-gateway:latest .

docker-run: ## Run Docker container
	docker run -p 8787:8787 -v $$(pwd)/data:/app/data --env-file .env agent-gateway:latest

docker-compose-up: ## Start all services with Docker Compose
	docker-compose up -d

docker-compose-down: ## Stop all services
	docker-compose down

docker-compose-logs: ## View logs from all services
	docker-compose logs -f

docs: ## Build documentation
	@echo "Documentation is in docs/ directory"
	@echo "View README.md and other .md files"

init-db: ## Initialize database
	python -c "from gateway.persistence.migrations import init_db; import asyncio; asyncio.run(init_db())"

migrate: ## Run database migrations
	alembic upgrade head

migrate-create: ## Create a new migration
	@read -p "Enter migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

setup-dev: dev-install init-db ## Set up development environment
	@echo "Development environment ready!"
	@echo "Run 'make run-dev' to start the gateway"

check: format-check lint test ## Run all checks (format, lint, test)

watch-test: ## Run tests in watch mode
	ptw --runner "pytest --testmon"

benchmark: ## Run performance benchmarks
	@echo "Benchmarks not yet implemented"

security-check: ## Run security checks
	pip-audit
	bandit -r gateway/

release-patch: ## Create a patch release
	bump2version patch

release-minor: ## Create a minor release
	bump2version minor

release-major: ## Create a major release
	bump2version major

.DEFAULT_GOAL := help
