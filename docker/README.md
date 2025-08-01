# Docker Setup for AegisTrader

This document describes how to build and run the AegisTrader applications using Docker.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- HTTP Proxy configured at `http://192.168.10.23:10809` (for builds in restricted networks)

## Services

The system consists of three main services:

1. **NATS JetStream** - Message broker and service registry
2. **Monitor API** - FastAPI management backend (port 8100, uses `uv` for faster Python package management)
3. **Monitor UI** - Next.js monitoring frontend (port 3100, with Tailwind CSS and TypeScript)

## Building Images

### Individual Image Build

Build FastAPI service:
```bash
export http_proxy=http://192.168.10.23:10809
export https_proxy=http://192.168.10.23:10809
docker build -f apps/monitor-api/Dockerfile -t aegistrader/monitor-api:latest .
```

Build Next.js UI:
```bash
export http_proxy=http://192.168.10.23:10809
export https_proxy=http://192.168.10.23:10809
docker build -f apps/monitor-ui/Dockerfile -t aegistrader/monitor-ui:latest .
```

### Using Docker Compose

Build all services:
```bash
docker-compose build
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

### Monitor API
- `NATS_URL`: NATS server connection URL (default: `nats://localhost:4222`)

### Monitor UI
- `NEXT_PUBLIC_API_URL`: Backend API URL (default: `http://localhost:8100`)
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

## Troubleshooting

### Build Issues

If builds fail due to network issues:
1. Verify proxy settings are correct
2. Check proxy connectivity: `curl -I http://192.168.10.23:10809`
3. Use China npm mirror: Already configured in Dockerfiles

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
- NATS: 4222 (standard)