# Current Kubernetes Environment State Documentation

## Overview
This document captures the complete state of the current Kubernetes deployment in the `aegis-trader` namespace, which must be preserved and considered during any Helm chart refactoring.

## Cluster Information
- **Kind Cluster**: aegis-local-control-plane (v1.27.3)
- **Namespace**: aegis-trader
- **Helm Release**: aegis-trader (revision 7, deployed)
- **Chart Version**: aegis-trader-0.1.0
- **App Version**: 0.1.0

## Deployed Resources

### 1. NATS Cluster (StatefulSet)
- **Name**: aegis-trader-nats
- **Type**: StatefulSet
- **Replicas**: 3 (all running)
- **Image**: nats:2.11.6-alpine
- **Resources**:
  - Requests: CPU 1, Memory 4Gi
  - Limits: CPU 2, Memory 8Gi
- **Environment Variables**:
  - GOMEMLIMIT: 7GiB
- **Persistent Storage**:
  - 3 PVCs, each 10Gi (standard storage class)
  - Mount path: /data (JetStream storage)
- **Services**:
  - ClusterIP Service: aegis-trader-nats (10.96.181.118:4222)
  - Headless Service: aegis-trader-nats-headless (for StatefulSet)
- **Ports**: 4222 (client), 6222 (cluster), 8222 (monitor)

### 2. Monitor API (Deployment)
- **Name**: aegis-trader-monitor-api
- **Type**: Deployment
- **Replicas**: 1
- **Image**: aegistrader-monitor-api:20250803-151359
- **Resources**:
  - Requests: CPU 1, Memory 2Gi
  - Limits: CPU 1, Memory 2Gi
- **Service**: ClusterIP 10.96.120.184:8100
- **ConfigMap Variables**:
  - API_PORT: "8100"
  - NATS_URL: "nats://aegis-trader-nats:4222"
  - NATS_KV_BUCKET: "service_registry"
- **Init Container**: wait-for-nats (busybox:1.36)

### 3. Monitor UI (Deployment)
- **Name**: aegis-trader-monitor-ui
- **Type**: Deployment
- **Replicas**: 1
- **Image**: aegistrader-monitor-ui:20250803-151359
- **Resources**:
  - Requests: CPU 500m, Memory 1Gi
  - Limits: CPU 500m, Memory 1Gi
- **Service**: ClusterIP 10.96.164.150:3100
- **Environment Variables**:
  - NEXT_PUBLIC_API_URL: (configured via ConfigMap)
  - PORT: "3100"
- **Init Container**: wait-for-api (busybox:1.36)

### 4. NATS Box (Deployment)
- **Name**: aegis-trader-nats-box
- **Type**: Deployment
- **Replicas**: 1
- **Purpose**: CLI tool for NATS administration

### 5. Jobs
- **Name**: aegis-trader-create-kv-bucket
- **Status**: Completed
- **Purpose**: Initialize NATS KV bucket for service registry

## Naming Conventions
All resources follow the pattern: `{helm-release-name}-{component}`
- aegis-trader-nats
- aegis-trader-monitor-api
- aegis-trader-monitor-ui
- aegis-trader-nats-box

## Labels Structure
All resources have consistent labeling:
```yaml
app.kubernetes.io/name: {component-name}
app.kubernetes.io/instance: aegis-trader
app.kubernetes.io/managed-by: Helm
app.kubernetes.io/version: {version}
helm.sh/chart: {chart-name-version}
meta.helm.sh/release-name: aegis-trader
meta.helm.sh/release-namespace: aegis-trader
```

## Image Management
- Images are built locally with Docker Compose
- Tagged with timestamp format: YYYYMMDD-HHMMSS
- Loaded into Kind cluster using: `docker save | docker exec -i {kind-node} ctr -n k8s.io images import -`
- Pull Policy: IfNotPresent

## Critical Dependencies
1. **Service Discovery**: All services depend on NATS being available
2. **Init Containers**: Used to ensure proper startup order
3. **KV Store**: Must be initialized before services can register

## Configuration Management
- Environment variables passed via:
  - ConfigMaps (for non-sensitive data)
  - Direct env vars in deployments
- No Secrets currently in use (future consideration for production)

## Networking
- All services use ClusterIP (no external exposure)
- Port forwarding handled by Makefile scripts
- Inter-service communication via DNS names

## Storage
- Only NATS uses persistent storage (JetStream)
- 10Gi per NATS instance
- Standard storage class (Kind default)

## Resource Allocation Summary
- **Total CPU Requests**: 3.5 cores (NATS: 3, API: 1, UI: 0.5)
- **Total Memory Requests**: 15Gi (NATS: 12Gi, API: 2Gi, UI: 1Gi)
- **Total Storage**: 30Gi (3x10Gi for NATS JetStream)

## Refactoring Considerations

### Must Preserve:
1. **Service Names**: Other services depend on DNS resolution
2. **Port Numbers**: Hardcoded in configurations
3. **NATS Configuration**: Critical for service registry functionality
4. **Label Selectors**: Used by services to find pods
5. **Init Container Logic**: Ensures proper startup sequence
6. **Resource Limits**: Tested and optimized for current workload

### Can Optimize:
1. **Image Building Process**: Currently timestamp-based, could use Git SHA
2. **ConfigMap Structure**: Could consolidate common configurations
3. **Helm Values Files**: Too many variants, needs consolidation
4. **Chart Dependencies**: Could use base charts for similar services

### Future Trading Services Requirements:
Based on Task 1 completion, trading services will need:
- Similar deployment structure as monitor-api
- Access to NATS for service registration
- Configurable instance counts (2-3 per service type)
- Service type configuration via environment variables
- Resource limits: CPU 100m-500m, Memory 128Mi-512Mi per instance
