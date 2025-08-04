# Build stage
FROM python:3.13-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy all necessary files from monorepo
COPY packages/aegis-sdk /build/packages/aegis-sdk
COPY packages/shared-contracts /build/packages/shared-contracts
COPY apps/trading-service /build/apps/trading-service

# Install dependencies
WORKDIR /build/apps/trading-service
RUN pip install --no-cache-dir -r requirements.txt

# Install local packages
RUN pip install --no-cache-dir /build/packages/shared-contracts
RUN pip install --no-cache-dir /build/packages/aegis-sdk

# Runtime stage
FROM python:3.13-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /build/apps/trading-service /app

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Command to run the service
CMD ["python", "main.py"]
