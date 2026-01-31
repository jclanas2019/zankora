# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e .[all]

# Stage 2: Runtime
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash gateway && \
    mkdir -p /app/data /app/plugins /app/logs && \
    chown -R gateway:gateway /app

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=gateway:gateway gateway/ ./gateway/
COPY --chown=gateway:gateway plugins/ ./plugins/
COPY --chown=gateway:gateway webchat/ ./webchat/
COPY --chown=gateway:gateway pyproject.toml ./

# Install application in editable mode
RUN pip install --no-cache-dir -e .

# Switch to non-root user
USER gateway

# Expose port
EXPOSE 8787

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8787/healthz', timeout=5).raise_for_status()" || exit 1

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AGW_DATA_DIR=/app/data \
    AGW_PLUGIN_DIR=/app/plugins

# Default command
CMD ["python", "-m", "gateway"]
