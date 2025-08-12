# Echo Service DDD - Kubernetes Deployment

This Helm chart deploys the echo-service-ddd application to Kubernetes.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- NATS deployed in the cluster
- Monitor API service deployed (optional)

## Installation

### Quick Start (Development)

```bash
# Install with default values
helm install echo-service ./k8s

# Install with development values
helm install echo-service ./k8s -f ./k8s/values-dev.yaml

# Install in a specific namespace
helm install echo-service ./k8s -n development --create-namespace
```

### Production Deployment

```bash
# Create namespace
kubectl create namespace production

# Create NATS authentication secret (if using authentication)
kubectl create secret generic nats-auth-secret \
  --from-literal=token=your-nats-token \
  -n production

# Install with production values
helm install echo-service ./k8s \
  -f ./k8s/values-prod.yaml \
  -n production
```

## Configuration

The following table lists the configurable parameters and their default values:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `2` |
| `image.repository` | Image repository | `echo-service-ddd` |
| `image.tag` | Image tag | `latest` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `service.type` | Service type | `ClusterIP` |
| `service.port` | Service port | `80` |
| `service.targetPort` | Container port | `8080` |
| `nats.url` | NATS server URL | `nats://nats:4222` |
| `nats.token` | NATS authentication token | `""` |
| `nats.secretName` | Secret containing NATS token | `""` |
| `monitorApi.url` | Monitor API URL | `http://monitor-api:8000` |
| `logLevel` | Application log level | `INFO` |
| `resources.limits` | Resource limits | `{cpu: 500m, memory: 512Mi}` |
| `resources.requests` | Resource requests | `{cpu: 100m, memory: 128Mi}` |
| `ingress.enabled` | Enable ingress | `false` |
| `livenessProbe.enabled` | Enable liveness probe | `true` |
| `readinessProbe.enabled` | Enable readiness probe | `true` |

## Upgrading

```bash
# Upgrade release with new values
helm upgrade echo-service ./k8s -f ./k8s/values-prod.yaml

# Upgrade with specific image tag
helm upgrade echo-service ./k8s --set image.tag=v2.0.0
```

## Uninstallation

```bash
# Uninstall the release
helm uninstall echo-service

# Uninstall from specific namespace
helm uninstall echo-service -n production
```

## Testing the Deployment

### Check Deployment Status

```bash
# Get pods
kubectl get pods -l app.kubernetes.io/name=echo-service-ddd

# Check logs
kubectl logs -l app.kubernetes.io/name=echo-service-ddd

# Describe deployment
kubectl describe deployment echo-service-echo-service-ddd
```

### Test Service Endpoints

```bash
# Port forward to test locally
kubectl port-forward service/echo-service-echo-service-ddd 8080:80

# Test health endpoint
curl http://localhost:8080/health

# Test echo endpoint (if exposed via HTTP)
curl -X POST http://localhost:8080/echo \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, World!"}'
```

## Troubleshooting

### Pod Not Starting

1. Check pod status:
   ```bash
   kubectl describe pod <pod-name>
   ```

2. Check logs:
   ```bash
   kubectl logs <pod-name>
   ```

3. Verify NATS connectivity:
   ```bash
   kubectl exec -it <pod-name> -- nc -zv nats 4222
   ```

### Service Not Accessible

1. Verify service endpoints:
   ```bash
   kubectl get endpoints echo-service-echo-service-ddd
   ```

2. Check service configuration:
   ```bash
   kubectl describe service echo-service-echo-service-ddd
   ```

### Configuration Issues

1. Verify ConfigMap:
   ```bash
   kubectl get configmap echo-service-echo-service-ddd-config -o yaml
   ```

2. Check environment variables in pod:
   ```bash
   kubectl exec <pod-name> -- env | grep -E "(NATS|MONITOR|SERVICE)"
   ```

## Development Tips

### Local Development with Minikube

```bash
# Start minikube
minikube start

# Build image locally
docker build -t echo-service-ddd:dev ../

# Load image into minikube
minikube image load echo-service-ddd:dev

# Install with dev values
helm install echo-service ./k8s -f ./k8s/values-dev.yaml
```

### Using Kind

```bash
# Create cluster
kind create cluster

# Build and load image
docker build -t echo-service-ddd:dev ../
kind load docker-image echo-service-ddd:dev

# Install chart
helm install echo-service ./k8s -f ./k8s/values-dev.yaml
```

## Environment-Specific Values

- `values.yaml` - Default production-ready values
- `values-dev.yaml` - Development environment with reduced resources
- `values-prod.yaml` - Production environment with HA configuration

## Security Considerations

1. **NATS Authentication**: Always use authentication tokens or certificates in production
2. **Network Policies**: Implement network policies to restrict traffic
3. **Pod Security**: Use security contexts and run as non-root user
4. **Secrets Management**: Use external secret operators for sensitive data
5. **RBAC**: Implement proper RBAC rules for ServiceAccounts

## Monitoring

The service exposes metrics and health endpoints:

- `/health` - Health check endpoint
- `/metrics` - Prometheus metrics (if enabled)

Configure Prometheus ServiceMonitor for automatic metrics collection:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: echo-service-ddd
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: echo-service-ddd
  endpoints:
    - port: http
      path: /metrics
```
