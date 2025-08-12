# Docker image definition
# Use Python 3.13+ as base image
FROM python:3.13-slim

# Accept proxy build arguments
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

# Set working directory
WORKDIR /app

# Set environment variables for Python and uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/packages \
    UV_CACHE_DIR=/tmp/uv-cache

# Install system dependencies and uv (this layer is cached)
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

# Install Python dependencies first (these rarely change)
RUN if [ -n "$HTTP_PROXY" ]; then \
      export http_proxy=$HTTP_PROXY && \
      export https_proxy=$HTTPS_PROXY && \
      export HTTP_PROXY=$HTTP_PROXY && \
      export HTTPS_PROXY=$HTTPS_PROXY && \
      export UV_HTTP_PROXY=$HTTP_PROXY && \
      export UV_HTTPS_PROXY=$HTTPS_PROXY; \
    fi && \
    uv pip install --system --no-cache \
    pydantic==2.10.0 \
    python-dateutil==2.8.2

# Copy and install the SDK packages (SDK changes trigger rebuild)
COPY packages/aegis-sdk /packages/aegis-sdk
COPY packages/aegis-sdk-dev /packages/aegis-sdk-dev
RUN if [ -n "$HTTP_PROXY" ]; then \
      export http_proxy=$HTTP_PROXY && \
      export https_proxy=$HTTPS_PROXY && \
      export HTTP_PROXY=$HTTP_PROXY && \
      export HTTPS_PROXY=$HTTPS_PROXY && \
      export UV_HTTP_PROXY=$HTTP_PROXY && \
      export UV_HTTPS_PROXY=$HTTPS_PROXY; \
    fi && \
    uv pip install --system --no-cache -e /packages/aegis-sdk && \
    uv pip install --system --no-cache -e /packages/aegis-sdk-dev

# Copy the specific project directory
# The actual path will be determined at build time
# Build context is always from AEGIS_ROOT
ARG PROJECT_PATH=.
COPY ${PROJECT_PATH}/ /app/

# Set environment variables
ENV SERVICE_NAME=test-example \
    SERVICE_VERSION=1.0.0 \
    LOG_LEVEL=INFO \
    ENVIRONMENT=development

# Run the application
CMD ["python", "main.py"]
