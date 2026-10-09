# Cloud Run Production Container for Verified GitHub Agent
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy configuration and install dependencies
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml || true

# Copy project source code
COPY . .

EXPOSE 8080

# Cloud Run execution entrypoint serving the ADK root_agent
CMD ["sh", "-c", "uv run python -m google.adk.server --host 0.0.0.0 --port ${PORT:-8080} blueprints.verified_github_agent.github_agent_runtime"]
