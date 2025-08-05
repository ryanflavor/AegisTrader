# AegisTrader

AegisTrader is an automated trading system built with modern microservices architecture. The system provides a comprehensive platform for service management, monitoring, and inter-service communication using NATS JetStream.

## Project Structure

- `apps/` - Application services
  - `monitor-api/` - FastAPI Management Service with CRUD operations for service definitions
  - `monitor-ui/` - Next.js Monitoring Frontend with real-time service status dashboard
  - `trading-service/` - Example trading services (Order, Pricing, Risk) demonstrating SDK usage
- `packages/` - Shared packages
  - `aegis-sdk/` - Core SDK with service registry, discovery, RPC, events, and metrics
  - `shared-contracts/` - Shared event contracts and utilities for type-safe communication
- `helm/` - Kubernetes Helm charts for deploying the entire system
- `tests/` - Comprehensive unit and integration test suites

## Features

### Completed (Through Story 2.4)

- ✅ **Service Registry & Heartbeats** - Automatic service registration with health monitoring
- ✅ **Service Discovery** - Dynamic service discovery with multiple selection strategies
- ✅ **Inter-Service RPC** - Type-safe RPC communication between services
- ✅ **Event Streaming** - Pub/sub event system with domain-based routing
- ✅ **Management API** - RESTful API for CRUD operations on service definitions
- ✅ **Monitoring Dashboard** - Real-time UI showing service health and status
- ✅ **Example Trading Services** - Order, Pricing, and Risk services demonstrating patterns
- ✅ **Kubernetes Integration** - Full Helm chart deployment with auto-scaling support
- ✅ **Metrics Collection** - Built-in metrics port for performance monitoring
- ✅ **Failover & Recovery** - Automatic pod recovery with service re-registration

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

### Quick Start

```bash
# Deploy to local Kind cluster
make dev-deploy

# Forward ports for local access
make dev-forward

# Check service registry status
make registry-status
```

### Service Management

Rapid development commands for updating individual services:

```bash
# Update specific services (~45 seconds each)
make update-api        # Update Monitor API only
make update-ui         # Update Monitor UI only
make update-order      # Update Order Service only
make update-pricing    # Update Pricing Service only
make update-risk       # Update Risk Service only

# Utility commands
make restart-all       # Restart all services
make watch            # Monitor pod status changes
```

For detailed Kubernetes deployment instructions, see `helm/README.md`.

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

## Architecture

### Core Components

1. **AegisSDK** - Python SDK providing:
   - Service registration with automatic heartbeats
   - Service discovery with caching and selection strategies
   - RPC client/server with request-reply patterns
   - Event publishing and subscription
   - Metrics collection and reporting

2. **NATS JetStream** - Message broker providing:
   - Key-Value store for service registry
   - Stream-based event distribution
   - Request-reply for RPC communication

3. **Monitor API** - Management service providing:
   - CRUD operations for service definitions
   - Service instance monitoring
   - RESTful API for UI and external tools

4. **Monitor UI** - Next.js dashboard showing:
   - Real-time service health status
   - Service instance details
   - Interactive service management

### Example Services

The project includes three example trading services:

- **Order Service** - Manages trading orders with RPC endpoints
- **Pricing Service** - Provides market pricing data and updates
- **Risk Service** - Assesses order risk and manages position limits

These services demonstrate best practices for using AegisSDK features.
