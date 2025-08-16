# Deploying Market Service with CTP Gateway

This guide explains how to deploy the market service with CTP gateway support.

## Prerequisites

1. Kubernetes cluster (Kind, Minikube, or production cluster)
2. kubectl configured to access your cluster
3. Valid CTP account credentials
4. NATS deployed in the cluster

## Setup Steps

### 1. Create CTP Credentials File

Copy the example environment file and add your CTP credentials:

```bash
cp .env.example .env.test.local
```

Edit `.env.test.local` with your CTP account details:

```bash
# CTP Account Information
CTP_REAL_USER_ID=your_user_id
CTP_REAL_PASSWORD=your_password
CTP_REAL_BROKER_ID=your_broker_id

# CTP Server Addresses (Primary)
CTP_REAL_TD_ADDRESS=tcp://your.td.server:port
CTP_REAL_MD_ADDRESS=tcp://your.md.server:port

# CTP Server Addresses (Secondary/Backup)
CTP_REAL_TD_ADDRESS_2=tcp://backup.td.server:port
CTP_REAL_MD_ADDRESS_2=tcp://backup.md.server:port

# Authentication (if required by your broker)
CTP_REAL_APP_ID=your_app_id
CTP_REAL_AUTH_CODE=your_auth_code
```

**Important**: Never commit `.env.test.local` to version control! It's already in `.gitignore`.

### 2. Deploy to Kubernetes

The deployment process is automated through the Makefile:

```bash
# Full deployment (build + secret + deploy)
make deploy-to-kind

# Fast deployment (uses cached Docker image)
make deploy-to-kind-fast
```

This will:
1. Build the Docker image
2. Load it to your Kind cluster (if using Kind)
3. **Create/update the K8s secret from `.env.test.local`** (automatic!)
4. Deploy using Helm

### 3. Manual Secret Management (if needed)

If you need to manually manage the secret:

```bash
# Create or update the secret
make create-secret

# Or directly with kubectl
kubectl create secret generic ctp-credentials \
  --from-env-file=.env.test.local \
  -n aegis-trader \
  --dry-run=client -o yaml | kubectl apply -f -

# Verify the secret
kubectl get secret ctp-credentials -n aegis-trader

# View secret contents (base64 encoded)
kubectl get secret ctp-credentials -n aegis-trader -o yaml
```

### 4. Enable/Disable CTP Gateway

Control whether CTP gateway is enabled via Helm values:

```yaml
# k8s/values.yaml
ctp:
  enabled: true  # Set to false to disable CTP gateway
```

Or override during deployment:

```bash
# Deploy with CTP disabled
helm upgrade market-service ./k8s \
  --set ctp.enabled=false \
  -n aegis-trader

# Deploy with CTP enabled (default)
helm upgrade market-service ./k8s \
  --set ctp.enabled=true \
  -n aegis-trader
```

### 5. Verify Deployment

Check pod status:

```bash
kubectl get pods -n aegis-trader
```

Check logs for CTP connection:

```bash
kubectl logs -l app.kubernetes.io/name=market-service -n aegis-trader --tail=50
```

Look for:
- "CTP Gateway Service initialized" (if enabled)
- "CTP connected" or "TD login success"
- "SingleActive: Acquired leadership" (for leader election)

### 6. High Availability Setup

For HA with leader election:

```bash
# Scale to multiple replicas
kubectl scale deployment market-service --replicas=3 -n aegis-trader

# Check which pod is the leader
kubectl logs -l app.kubernetes.io/name=market-service -n aegis-trader | grep -i leader
```

Only the leader pod will connect to CTP, while others remain in standby.

## Troubleshooting

### Secret Not Found

If you see "secret not found" errors:

```bash
# Ensure secret exists
kubectl get secrets -n aegis-trader | grep ctp-credentials

# Recreate if missing
make create-secret
```

### CTP Connection Failed

Check environment variables in pod:

```bash
kubectl exec -it <pod-name> -n aegis-trader -- env | grep CTP
```

### Leader Election Issues

For leader election problems:

```bash
# Check NATS connectivity
kubectl port-forward -n aegis-trader svc/aegis-trader-nats 4222:4222

# Verify service registry KV bucket
nats kv list
```

## Security Notes

1. **Never hardcode credentials** in values.yaml or ConfigMaps
2. Use Kubernetes Secrets for sensitive data
3. Consider using external secret managers (Vault, AWS Secrets Manager) in production
4. Rotate credentials regularly
5. Use RBAC to limit secret access

## Production Considerations

For production deployments:

1. Use external secret management solutions
2. Enable TLS for CTP connections (if supported)
3. Set up monitoring and alerting for CTP connectivity
4. Configure appropriate resource limits
5. Use dedicated namespaces with network policies
6. Implement proper backup and disaster recovery for stateful data
