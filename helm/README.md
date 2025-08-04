# Refactored Helm Charts for AegisTrader

This directory contains the refactored Helm charts with improved structure and maintainability.

## Key Improvements

### 1. Base Microservice Chart
- Created reusable `base-microservice` chart for common patterns
- Reduces duplication across similar services
- Easily extensible for new services

### 2. Simplified Dependencies
Using Helm aliases to deploy multiple instances of the base chart:
```yaml
dependencies:
  - name: base-microservice
    alias: monitor-api
  - name: base-microservice
    alias: order-service
  - name: base-microservice
    alias: pricing-service
  - name: base-microservice
    alias: risk-service
```

### 3. Consolidated Values Files
Reduced from 15+ files to 4 essential files:
- `values.yaml` - Base defaults for all environments
- `values-dev.yaml` - Development overrides (reduced resources)
- `values-staging.yaml` - Staging environment settings
- `values-prod.yaml` - Production settings

### 4. Trading Services Support
Pre-configured for all trading services:
- Order Service (3 replicas)
- Pricing Service (2 replicas)
- Risk Service (2 replicas)

## Migration Guide

### 1. Test in Separate Namespace
```bash
cd helm-refactored
make install  # Installs to aegis-trader-test namespace
```

### 2. Verify Services
```bash
make status
kubectl get pods -n aegis-trader-test
```

### 3. Compare with Existing
```bash
# Port forward and test
kubectl port-forward -n aegis-trader-test svc/aegis-trader-refactored-monitor-api 8101:8100
kubectl port-forward -n aegis-trader-test svc/aegis-trader-refactored-monitor-ui 3101:3100
```

### 4. Replace Production
Once validated:
```bash
# Backup current helm
mv helm helm-backup

# Move refactored to production
mv helm-refactored helm

# Update Makefile references if needed
```

## Structure Overview

```
helm-refactored/
├── Chart.yaml              # Main chart with dependencies
├── values.yaml             # Default values
├── values-dev.yaml         # Dev environment
├── charts/
│   ├── base-microservice/  # Reusable base chart
│   ├── monitor-ui/         # Custom UI chart
│   └── nats/              # External NATS chart
└── templates/
    ├── _helpers.tpl
    ├── nats-kv-job.yaml   # Post-install job
    └── NOTES.txt          # Installation notes
```

## Benefits

1. **Maintainability**: Update base chart once, all services benefit
2. **Scalability**: Add new services with minimal configuration
3. **Consistency**: All microservices follow same patterns
4. **Flexibility**: Override any value per service as needed
5. **Simplicity**: Fewer files to manage and understand

## Trading Services Configuration

Each trading service can be configured independently:

```yaml
order-service:
  enabled: true
  replicaCount: 3
  image:
    repository: aegistrader-trading-service
    tag: "latest"
  env:
    - name: SERVICE_TYPE
      value: "ORDER"
```

## Resource Management

Development environment uses reduced resources:
- NATS: 1 replica instead of 3
- Services: Lower CPU/memory limits
- Trading services: 1 replica each

Production can scale up via values-prod.yaml.

## Commands

```bash
make help         # Show all commands
make deps         # Update dependencies
make lint         # Validate charts
make template     # Preview generated YAML
make install      # Install to test namespace
make upgrade      # Upgrade existing
make uninstall    # Remove installation
make status       # Check deployment status
```
