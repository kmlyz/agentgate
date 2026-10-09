# Multi-stage lean production image for AgentGate
FROM python:3.12-slim AS builder

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1

# Install uv for fast dependency builds
RUN pip install --no-cache-dir uv

# Build dependencies layer
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY blueprints/ ./blueprints/
RUN uv pip install --system --no-cache .

# Production runtime stage
FROM python:3.12-slim AS runner

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=sse
ENV PORT=8000
ENV HOST=0.0.0.0

# Create secure unprivileged service user
RUN groupadd -g 10001 agentgate && \
    useradd -u 10001 -g agentgate -m -s /bin/bash appuser

# Copy installed system packages and binaries from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create storage directory for proposals and set permissions
RUN mkdir -p /app/.tmp && chown -R appuser:agentgate /app

USER appuser

EXPOSE 8000

# Default entrypoint serves MCP over SSE, but allows overriding to agentgate CLI
ENTRYPOINT ["agentgate-mcp"]
CMD []
