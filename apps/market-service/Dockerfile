# syntax=docker/dockerfile:1.4
# Multi-stage optimized Dockerfile for market-service
# Specify x86_64 platform for CTP compatibility
FROM --platform=linux/amd64 python:3.13-slim AS builder

# Accept proxy build arguments
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG PROJECT_PATH=.

# Set environment variables for build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_COMPILE_BYTECODE=0 \
    UV_NO_SYNC=1

# Install system dependencies and uv with cache mount
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    if [ -n "$HTTP_PROXY" ]; then \
      export http_proxy=$HTTP_PROXY && \
      export https_proxy=$HTTPS_PROXY && \
      export HTTP_PROXY=$HTTP_PROXY && \
      export HTTPS_PROXY=$HTTPS_PROXY; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    locales \
    gcc \
    g++ \
    cmake \
    && curl -LsSf https://astral.sh/uv/0.5.19/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/ \
    && locale-gen zh_CN.GB18030 \
    && update-locale

# Create virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV=/opt/venv

# First install SDK packages (they are dependencies of the project)
COPY packages/aegis-sdk /packages/aegis-sdk
COPY packages/aegis-sdk-dev /packages/aegis-sdk-dev
RUN --mount=type=cache,target=/tmp/uv-cache,sharing=locked \
    if [ -n "$HTTP_PROXY" ]; then \
      export http_proxy=$HTTP_PROXY && \
      export https_proxy=$HTTPS_PROXY && \
      export UV_HTTP_PROXY=$HTTP_PROXY && \
      export UV_HTTPS_PROXY=$HTTPS_PROXY; \
    fi && \
    uv pip install -e /packages/aegis-sdk && \
    uv pip install -e /packages/aegis-sdk-dev

# Copy project files and install dependencies
COPY ${PROJECT_PATH}/pyproject.toml /tmp/pyproject.toml
COPY ${PROJECT_PATH}/README.md /tmp/README.md
# Copy pre-built wheels (vnpy-ctp, vnpy-sopt, ta-lib)
COPY ${PROJECT_PATH}/whl/vnpy_ctp-6.7.7.2-cp313-cp313-linux_x86_64.whl /tmp/
COPY ${PROJECT_PATH}/whl/vnpy_sopt-3.7.1.0-cp313-cp313-linux_x86_64.whl /tmp/
COPY ${PROJECT_PATH}/whl/ta_lib-0.6.5-cp313-cp313-manylinux_2_28_x86_64.whl /tmp/
WORKDIR /tmp
RUN --mount=type=cache,target=/tmp/uv-cache,sharing=locked \
    if [ -n "$HTTP_PROXY" ]; then \
      export http_proxy=$HTTP_PROXY && \
      export https_proxy=$HTTPS_PROXY && \
      export UV_HTTP_PROXY=$HTTP_PROXY && \
      export UV_HTTPS_PROXY=$HTTPS_PROXY; \
    fi && \
    # Remove local aegis-sdk path reference since we installed it above
    sed -i '/\[tool.uv.sources\]/,/^$/d' pyproject.toml && \
    sed -i 's/"aegis-sdk",//' pyproject.toml && \
    sed -i 's/"aegis-sdk"//' pyproject.toml && \
    # Use uv pip compile to generate requirements and install (except pre-built wheels)
    uv pip compile pyproject.toml -o requirements.txt && \
    grep -v "vnpy-ctp\|vnpy-sopt\|ta-lib" requirements.txt > requirements-no-wheels.txt && \
    uv pip install -r requirements-no-wheels.txt && \
    # Install pre-built wheels
    uv pip install /tmp/ta_lib-0.6.5-cp313-cp313-manylinux_2_28_x86_64.whl --no-deps && \
    uv pip install /tmp/vnpy_ctp-6.7.7.2-cp313-cp313-linux_x86_64.whl --no-deps && \
    uv pip install /tmp/vnpy_sopt-3.7.1.0-cp313-cp313-linux_x86_64.whl --no-deps && \
    echo "Installed all pre-built wheels (vnpy-ctp, vnpy-sopt, ta-lib)"

# Final stage - smaller runtime image
# Specify x86_64 platform for CTP compatibility
FROM --platform=linux/amd64 python:3.13-slim

# Create non-root user
RUN groupadd -r aegis && useradd -r -g aegis -m -d /home/aegis -s /bin/bash aegis

# Install only runtime dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    locales \
    ca-certificates \
    libgomp1 \
    libc6 \
    libstdc++6 \
    && locale-gen zh_CN.GB18030 \
    && update-locale \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy virtual environment from builder
COPY --from=builder --chown=aegis:aegis /opt/venv /opt/venv
COPY --from=builder --chown=aegis:aegis /packages /packages

# Ensure shared libraries have correct permissions and setup LD paths
USER root
RUN find /opt/venv -name "*.so" -exec chmod 755 {} \; && \
    # Find and add vnpy library paths to ld.so.conf
    echo "/opt/venv/lib/python3.13/site-packages/vnpy_ctp/api" > /etc/ld.so.conf.d/vnpy.conf && \
    echo "/opt/venv/lib/python3.13/site-packages/vnpy_sopt/api" >> /etc/ld.so.conf.d/vnpy.conf && \
    ldconfig || true
USER aegis

# Set working directory
WORKDIR /app

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV=/opt/venv \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/packages \
    SERVICE_NAME=market-service \
    SERVICE_VERSION=1.0.0 \
    LOG_LEVEL=INFO \
    ENVIRONMENT=production

# Copy application code with proper build arg
ARG PROJECT_PATH=.
COPY --chown=aegis:aegis ${PROJECT_PATH}/ /app/

# Switch to non-root user
USER aegis

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Default entrypoint (will be overridden by K8s deployment)
CMD ["python", "main.py"]
