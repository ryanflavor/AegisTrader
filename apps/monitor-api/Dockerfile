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

# Install system dependencies and uv (这一层很少变化，会被缓存)
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

# Install FastAPI and production dependencies first (这些依赖很少变化)
RUN if [ -n "$HTTP_PROXY" ]; then \
      export http_proxy=$HTTP_PROXY && \
      export https_proxy=$HTTPS_PROXY && \
      export HTTP_PROXY=$HTTP_PROXY && \
      export HTTPS_PROXY=$HTTPS_PROXY && \
      export UV_HTTP_PROXY=$HTTP_PROXY && \
      export UV_HTTPS_PROXY=$HTTPS_PROXY; \
    fi && \
    uv pip install --system --no-cache \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    pydantic==2.10.0 \
    python-multipart==0.0.12 \
    httpx==0.28.0

# Copy requirements file if it exists (requirements.txt 变化时才会重新构建)
COPY apps/monitor-api/requirements.txt* /app/

# Install additional requirements if file exists
RUN if [ -n "$HTTP_PROXY" ]; then \
      export http_proxy=$HTTP_PROXY && \
      export https_proxy=$HTTPS_PROXY && \
      export HTTP_PROXY=$HTTP_PROXY && \
      export HTTPS_PROXY=$HTTPS_PROXY && \
      export UV_HTTP_PROXY=$HTTP_PROXY && \
      export UV_HTTPS_PROXY=$HTTPS_PROXY; \
    fi && \
    if [ -f requirements.txt ]; then uv pip install --system --no-cache -r requirements.txt; fi

# Copy and install the aegis-sdk package (SDK 变化时才会重新构建)
COPY packages/aegis-sdk /packages/aegis-sdk
RUN if [ -n "$HTTP_PROXY" ]; then \
      export http_proxy=$HTTP_PROXY && \
      export https_proxy=$HTTPS_PROXY && \
      export HTTP_PROXY=$HTTP_PROXY && \
      export HTTPS_PROXY=$HTTPS_PROXY && \
      export UV_HTTP_PROXY=$HTTP_PROXY && \
      export UV_HTTPS_PROXY=$HTTPS_PROXY; \
    fi && \
    uv pip install --system --no-cache -e /packages/aegis-sdk

# Copy application code (只有应用代码变化时才会重新构建这一层)
COPY apps/monitor-api/ /app/

# Expose the FastAPI port (using non-default port to avoid conflicts)
ARG API_PORT=8100
ENV API_PORT=${API_PORT}
EXPOSE ${API_PORT}

# Run the application with uvicorn (async-compatible production server)
# Using --workers 1 to ensure single process for proper async handling
CMD uvicorn app.main:app --host 0.0.0.0 --port ${API_PORT} --workers 1
