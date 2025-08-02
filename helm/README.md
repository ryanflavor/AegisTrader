# AegisTrader Helm Charts

This directory contains Helm charts for deploying the AegisTrader system to Kubernetes.

## Prerequisites

- Kubernetes cluster 1.28+ (supports native sidecar containers)
- Helm 3.x installed
- kubectl configured to access your cluster
- Docker images built from Story 0.1 available locally or in a registry

## Quick Start

### Local Development Deployment

1. **Install with development values:**
   ```bash
   make dev-install
   ```

2. **Access the services:**
   ```bash
   make port-forward NAMESPACE=aegis-dev
   ```
   - UI: http://localhost:3100
   - API: http://localhost:8100

3. **Check deployment status:**
   ```bash
   make status NAMESPACE=aegis-dev
   ```

### Production Deployment

1. **Install with default values:**
   ```bash
   make install
   ```

2. **Or install with custom values:**
   ```bash
   make install VALUES_FILE=values.prod.yaml NAMESPACE=production
   ```

## Chart Structure

```
helm/
├── Chart.yaml              # Parent chart metadata
├── Chart.lock              # Locked dependency versions
├── values.yaml             # Default configuration values
├── values.dev.yaml         # Development overrides
├── templates/              # Parent chart templates
│   ├── _helpers.tpl        # Reusable template helpers
│   ├── namespace.yaml      # Optional namespace creation
│   ├── nats-kv-job.yaml    # NATS KV bucket creation job
│   └── NOTES.txt           # Post-install instructions
├── charts/                 # Subcharts
│   ├── monitor-api/        # FastAPI Management Service
│   └── monitor-ui/         # Next.js Monitor UI
└── Makefile                # Deployment automation
```

## Configuration

### Key Configuration Options

```yaml
# NATS Cluster Configuration
nats:
  enabled: true
  replicas: 3                    # HA configuration
  nats:
    jetstream:
      enabled: true
      fileStorage:
        size: 10Gi               # Production storage
    resources:
      requests:
        cpu: "2"
        memory: 8Gi

# Management Service (FastAPI)
monitor-api:
  enabled: true
  replicaCount: 1
  service:
    port: 8100
  env:
    NATS_URL: "nats://{{ .Release.Name }}-nats:4222"
    NATS_KV_BUCKET: "service-registry"

# Monitor UI (Next.js)
monitor-ui:
  enabled: true
  replicaCount: 1
  service:
    port: 3100
  ingress:
    enabled: false               # Enable for external access
```

### Development vs Production

Development values (`values.dev.yaml`):
- Single NATS replica
- Reduced resource requirements
- Local storage configuration
- Ingress enabled for `aegis-trader.local`

Production values (customize as needed):
- 3 NATS replicas for HA
- Full resource allocations
- Production storage class
- TLS-enabled ingress

## Common Operations

### Install/Upgrade/Uninstall

```bash
# Install
make install

# Upgrade existing deployment
make upgrade

# Uninstall
make uninstall

# Complete cleanup including namespace
make clean
```

### Debugging and Troubleshooting

```bash
# Lint charts before deployment
make lint

# Generate and review manifests
make template

# Dry-run installation
make dry-run

# View logs from all pods
make logs

# Run Helm tests
make test
```

### Working with Different Environments

```bash
# Development
make dev-install
make dev-upgrade
make dev-uninstall

# Staging (example)
make install NAMESPACE=staging VALUES_FILE=values.staging.yaml

# Production (example)
make install NAMESPACE=production VALUES_FILE=values.prod.yaml
```

## Customization Guide

### Using Custom Values

Create your own values file:
```yaml
# my-values.yaml
nats:
  replicas: 5

monitor-api:
  replicaCount: 3
  resources:
    requests:
      cpu: 2000m
      memory: 4Gi
```

Deploy with custom values:
```bash
make install VALUES_FILE=my-values.yaml
```

### Modifying Image Locations

If your images are in a registry:
```yaml
monitor-api:
  image:
    repository: myregistry.io/aegis-trader/monitor-api
    tag: "v1.0.0"
    pullPolicy: Always

monitor-ui:
  image:
    repository: myregistry.io/aegis-trader/monitor-ui
    tag: "v1.0.0"
```

### Enabling Ingress

```yaml
monitor-ui:
  ingress:
    enabled: true
    className: nginx
    hosts:
      - host: aegis-trader.example.com
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: aegis-trader-tls
        hosts:
          - aegis-trader.example.com
```

## Troubleshooting

### NATS Connection Issues

1. Check NATS pods are running:
   ```bash
   kubectl get pods -n aegis-trader -l app.kubernetes.io/name=nats
   ```

2. Verify JetStream is enabled:
   ```bash
   kubectl exec -it aegis-trader-nats-0 -n aegis-trader -- nats server check jetstream
   ```

3. Check KV bucket creation:
   ```bash
   kubectl logs -n aegis-trader -l app.kubernetes.io/component=nats-kv-setup
   ```

### Service Connectivity

1. Verify services are created:
   ```bash
   kubectl get svc -n aegis-trader
   ```

2. Test internal connectivity:
   ```bash
   kubectl run test-pod --image=busybox -it --rm -- /bin/sh
   # Inside the pod:
   nc -vz aegis-trader-nats 4222
   nc -vz aegis-trader-monitor-api 8100
   ```

### Image Pull Issues

For local images:
1. Ensure images exist locally:
   ```bash
   docker images | grep aegis-trader
   ```

2. Use `imagePullPolicy: IfNotPresent` in values

For registry images:
1. Create image pull secret if needed
2. Add to `imagePullSecrets` in values

## Notes

- NATS service registration is NOT implemented yet (will be in Epic 2)
- The charts use init containers to ensure proper startup order
- Resource limits are configured for predictable performance
- Health checks are configured for all services
- The NATS KV bucket is created automatically via a Helm hook
