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

## CI/CD Setup

The project includes GitHub Actions CI/CD pipeline for automated testing and deployment.

### Quick Setup

1. **Configure Kubernetes access for CI/CD:**
   ```bash
   ./scripts/setup-ci-cd.sh
   ```

2. **Add the KUBE_CONFIG secret to GitHub:**
   - Go to Settings → Secrets and variables → Actions
   - Add `KUBE_CONFIG` secret with the content from `scripts/ci-kubeconfig.b64`

3. **Pipeline will automatically:**
   - Run tests on all pull requests
   - Build and push Docker images on main branch
   - Deploy to staging environment

For detailed setup instructions, see [docs/github-actions-setup.md](docs/github-actions-setup.md).