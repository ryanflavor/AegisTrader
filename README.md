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

### Setup

```bash
# Sync dependencies
uv sync

# Set up pre-commit hooks
./scripts/setup-pre-commit.sh

# Run tests
uv run pytest
```

### Pre-commit Hooks

This project uses pre-commit hooks to ensure code quality. The hooks will automatically run on every commit to:
- Format code with Black and isort
- Lint with Ruff and MyPy
- Check for security issues
- Validate file formats (YAML, JSON, etc.)
- Ensure proper commit messages

To run hooks manually:
```bash
pre-commit run --all-files
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
