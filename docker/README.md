# Docker Setup for AegisTrader

## Quick Start

```bash
# 1. Setup environment
cp .env.example .env

# 2. Start all services
docker-compose up -d

# 3. Access services
# - UI: http://localhost:3100
# - API: http://localhost:8100
# - NATS: http://localhost:8222
```

## Services

| Service | Tech Stack | Port | Description |
|---------|-----------|------|-------------|
| NATS | JetStream 2.10 | 4222, 8222 | Message broker |
| Monitor API | Python 3.13 + FastAPI | 8100 | Backend with health checks |
| Monitor UI | Node 20 + Next.js 14 | 3100 | Frontend with Tailwind CSS |

## Common Commands

```bash
# Build
docker-compose build

# View logs
docker-compose logs -f [service-name]

# Stop
docker-compose down

# Clean up
docker system prune -a
```

## Configuration

### Proxy Setup (.env file)
```
HTTP_PROXY=http://your-proxy:port
HTTPS_PROXY=http://your-proxy:port
NO_PROXY=localhost,127.0.0.1,nats,monitor-api,monitor-ui
```

### Health Check
```bash
curl http://localhost:8100/health
curl http://localhost:8100/ready
```

## Troubleshooting

- **Build fails**: Check proxy in `.env`
- **Connection issues**: Use service names (e.g., `nats`) not `localhost`
- **Port conflicts**: Change ports in `docker-compose.yaml`
