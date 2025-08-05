# Dockerfile for sticky service test
FROM python:3.13-slim

# Accept proxy build arguments
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

# Set working directory
WORKDIR /app

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies and curl for uv (with proxy support)
RUN if [ -n "$HTTP_PROXY" ]; then \
      export http_proxy=$HTTP_PROXY && \
      export https_proxy=$HTTPS_PROXY && \
      export HTTP_PROXY=$HTTP_PROXY && \
      export HTTPS_PROXY=$HTTPS_PROXY; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/ \
    && rm -rf /var/lib/apt/lists/*

# Copy the aegis-sdk package structure
COPY aegis_sdk /app/aegis_sdk
COPY tests /app/tests
COPY pyproject.toml /app/
COPY README.md /app/

# Install aegis-sdk using uv (with proxy support)
RUN if [ -n "$HTTP_PROXY" ]; then \
      export http_proxy=$HTTP_PROXY && \
      export https_proxy=$HTTPS_PROXY && \
      export HTTP_PROXY=$HTTP_PROXY && \
      export HTTPS_PROXY=$HTTPS_PROXY && \
      export UV_HTTP_PROXY=$HTTP_PROXY && \
      export UV_HTTPS_PROXY=$HTTPS_PROXY; \
    fi && \
    uv pip install --system --no-cache -e /app

# Run the sticky service
CMD ["python", "/app/tests/integration/k8s/sticky_service_runner.py"]
