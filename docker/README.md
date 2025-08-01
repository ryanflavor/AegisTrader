# Docker Setup for AegisTrader

This document describes how to build and run the AegisTrader applications using Docker.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- (Optional) HTTP Proxy for builds in restricted networks

## Quick Start

1. **Create `.env` file** (copy from `.env.example`):
```bash
cp .env.example .env
# Edit .env to set your proxy if needed
```

2. **Build and start all services**:
```bash
docker-compose up -d
```

3. **Access the services**:
- Monitor UI: http://localhost:3100
- Monitor API: http://localhost:8100
- NATS Monitoring: http://localhost:8222

## Services

The system consists of three main services:

1. **NATS JetStream** (`nats:2.10-alpine`)
   - Message broker and service registry
   - Ports: 4222 (client), 8222 (monitoring)
   
2. **Monitor API** (Python 3.13 + FastAPI)
   - Management backend with NATS integration
   - Port: 8100
   - Features: Health checks, readiness probes, structured logging
   - Uses `uv` for fast Python package management
   
3. **Monitor UI** (Node 20 + Next.js 14)
   - Monitoring frontend
   - Port: 3100
   - Features: Tailwind CSS, TypeScript, Shadcn/ui ready

## Building Images

### Using Docker Compose (Recommended)

Docker Compose automatically reads proxy settings from `.env` file:

```bash
# Build all services
docker-compose build

# Build specific service
docker-compose build monitor-api
docker-compose build monitor-ui
```

### Individual Image Build

For manual builds without docker-compose:

```bash
# Set proxy if needed
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port

# Build FastAPI service
docker build -f apps/monitor-api/Dockerfile -t aegistrader/monitor-api:latest .

# Build Next.js UI  
docker build -f apps/monitor-ui/Dockerfile -t aegistrader/monitor-ui:latest .
```

### Proxy Configuration

If you're behind a corporate proxy, configure it in `.env`:

```bash
# .env file
HTTP_PROXY=http://192.168.10.23:10809
HTTPS_PROXY=http://192.168.10.23:10809
NO_PROXY=localhost,127.0.0.1,nats,monitor-api,monitor-ui
```

## Running Services

### Using Docker Compose (Recommended)

Start all services:
```bash
docker-compose up -d
```

Stop all services:
```bash
docker-compose down
```

View logs:
```bash
docker-compose logs -f
```

### Individual Container Run

Run NATS:
```bash
docker run -d --name nats \
  -p 4222:4222 -p 8222:8222 \
  nats:2.10-alpine -js -m 8222
```

Run Monitor API:
```bash
docker run -d --name monitor-api \
  -p 8100:8100 \
  -e NATS_URL=nats://host.docker.internal:4222 \
  aegistrader/monitor-api:latest
```

Run Monitor UI:
```bash
docker run -d --name monitor-ui \
  -p 3100:3100 \
  -e NEXT_PUBLIC_API_URL=http://localhost:8100 \
  aegistrader/monitor-ui:latest
```

## Environment Variables

### Build-time Variables (in `.env`)
- `HTTP_PROXY`: HTTP proxy for package downloads
- `HTTPS_PROXY`: HTTPS proxy for package downloads  
- `NO_PROXY`: Hosts to bypass proxy

### Runtime Variables

#### Monitor API
- `NATS_URL`: NATS server connection URL (default: `nats://nats:4222`)
- `LOG_LEVEL`: Logging level (default: `INFO`)

#### Monitor UI
- `NEXT_PUBLIC_API_URL`: Backend API URL (default: `http://monitor-api:8100`)
- `PORT`: Next.js server port (default: `3100`)

## Health Checks

Monitor API health endpoint:
```bash
curl http://localhost:8100/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "management-service",
  "version": "0.1.0",
  "nats_url": "nats://nats:4222"
}
```

Readiness check (for Kubernetes):
```bash
curl http://localhost:8100/ready
```

Expected response:
```json
{
  "status": "ready"
}
```

## Network Configuration

All services run on a custom bridge network `aegis-network` for internal communication.

Service discovery:
- `nats`: NATS server
- `monitor-api`: FastAPI backend
- `monitor-ui`: Next.js frontend

## Development Workflow

### Hot Reload Development

For local development with hot reload:

```bash
# Start only infrastructure services
docker-compose up -d nats

# Run apps locally
cd apps/monitor-api && uvicorn app.main:app --reload --port 8100
cd apps/monitor-ui && npm run dev
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f monitor-api

# Last 100 lines
docker-compose logs --tail=100 monitor-api
```

## Troubleshooting

### Build Issues

If builds fail due to network issues:
1. Check `.env` file exists and has correct proxy settings
2. Verify proxy connectivity: `curl -I $HTTP_PROXY`
3. Clear Docker build cache: `docker-compose build --no-cache`
4. The Dockerfiles use:
   - China npm mirror (registry.npmmirror.com) for faster downloads
   - `uv` tool for faster Python package installation

### Runtime Issues

Check container logs:
```bash
docker logs <container-name>
```

Verify network connectivity:
```bash
docker exec monitor-api ping nats
```

### Port Conflicts

The services use non-default ports to avoid conflicts:
- FastAPI: 8100 (instead of 8000)
- Next.js: 3100 (instead of 3000)
- NATS: 4222 (client), 8222 (monitoring)

To change ports, modify `docker-compose.yaml` or use environment variables:
```bash
# Custom port mapping
PORT=3200 docker-compose up -d monitor-ui
```

### Common Issues

1. **Container can't connect to NATS**
   - Ensure all services are on the same Docker network
   - Use service names (e.g., `nats`) not `localhost`

2. **Slow builds**
   - Enable Docker BuildKit: `export DOCKER_BUILDKIT=1`
   - Use `.env` file for proxy configuration
   - Consider using `docker-compose build --parallel`

3. **Out of disk space**
   ```bash
   # Clean up Docker resources
   docker system prune -a
   ```

## Production Deployment

For production deployment:

1. Use specific image tags instead of `latest`
2. Set proper resource limits in docker-compose.yaml
3. Use Docker secrets for sensitive data
4. Enable health checks for container orchestration
5. Consider using Kubernetes with the provided health/ready endpoints