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
    UV_CACHE_DIR=/tmp/uv-cache

# Install system dependencies and uv with proxy support
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

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies with proxy support
RUN if [ -n "$HTTP_PROXY" ]; then \
      export http_proxy=$HTTP_PROXY && \
      export https_proxy=$HTTPS_PROXY && \
      export HTTP_PROXY=$HTTP_PROXY && \
      export HTTPS_PROXY=$HTTPS_PROXY && \
      export UV_HTTP_PROXY=$HTTP_PROXY && \
      export UV_HTTPS_PROXY=$HTTPS_PROXY; \
    fi && \
    uv pip install --system --no-cache -r requirements.txt

# Copy application code
COPY . .

# Expose service port
EXPOSE 8080

# Set environment variables for K8s deployment
ENV PYTHONUNBUFFERED=1 \
    SERVICE_NAME=echo-service-ddd \
    SERVICE_PORT=8080 \
    NATS_URL=nats://aegis-trader-nats.aegis-trader.svc.cluster.local:4222 \
    MONITOR_API_URL=http://aegis-trader-monitor-api.aegis-trader.svc.cluster.local:8100

# Run the service
CMD ["python", "main.py"]
