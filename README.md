# AegisTrader

AegisTrader is an automated trading system built with modern microservices architecture.

## Project Structure

- `apps/` - Application services
  - `monitor-api/` - FastAPI Management Service
  - `monitor-ui/` - Next.js Monitoring Frontend
- `packages/` - Shared packages
  - `aegis-sdk/` - Core SDK
  - `shared-contracts/` - Shared data contracts
- `helm/` - Kubernetes Helm charts
- `tests/` - Test suites

## Development

This project uses [uv](https://github.com/astral-sh/uv) for Python dependency management.

```bash
# Sync dependencies
uv sync

# Run tests
uv run pytest
```

## Deployment

See `helm/README.md` for Kubernetes deployment instructions.