# Version comments for key dependencies
# python:3.11-slim - v3.11
# poetry - v1.5.1
# build-essential - latest from apt
# curl - latest from apt
# ca-certificates - latest from apt

# ===== Builder Stage =====
FROM python:3.11-slim AS builder

# Set environment variables for builder stage
ENV POETRY_VERSION=1.5.1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    DEBIAN_FRONTEND=noninteractive

# Update system and install security patches and build dependencies
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    # Install poetry
    && curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install production dependencies only
RUN poetry install --no-dev --no-root \
    # Clean up build artifacts and caches
    && find /usr/local -type d -name __pycache__ -exec rm -rf {} + \
    && rm -rf ~/.cache/pip ~/.cache/poetry

# ===== Production Stage =====
FROM python:3.11-slim

# Set production environment variables
ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    DEBIAN_FRONTEND=noninteractive

# Update system and install runtime dependencies
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    # Create non-root user
    && groupadd -r memoryagent \
    && useradd -r -g memoryagent -s /bin/false memoryagent \
    # Create necessary directories
    && mkdir -p /app/data /app/logs \
    && chown -R memoryagent:memoryagent /app

# Set working directory
WORKDIR /app

# Copy dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy application code
COPY --chown=memoryagent:memoryagent src/ /app/src/

# Set secure permissions
RUN chmod -R 550 /app/src \
    && chmod -R 770 /app/data /app/logs

# Configure resource limits
LABEL maintainer="Memory Agent Team" \
      version="1.0.0" \
      environment="production" \
      service="memory-agent-backend"

# Expose application port
EXPOSE 8000

# Set up volumes for persistent storage
VOLUME ["/app/data", "/app/logs"]

# Configure healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl --fail http://localhost:8000/health || exit 1

# Switch to non-root user
USER memoryagent

# Set entrypoint with production configuration
ENTRYPOINT ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--log-config", "/app/src/logging.conf"]

# Apply security options
# Note: These are applied through docker run or compose file:
# --security-opt no-new-privileges=true
# --security-opt read-only=true
# --security-opt seccomp=default
# --cap-drop ALL
# --memory=16g
# --cpus=8
# --pids-limit=1000
# --ulimit nofile=65535