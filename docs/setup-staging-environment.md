# Setting Up Staging Environment for AegisTrader

This guide will help you configure the staging environment for automated deployments.

## Prerequisites

1. A Kubernetes cluster for staging (can be local k3s, minikube, or cloud-based)
2. kubectl configured to access your cluster
3. GitHub repository admin access

## Step 1: Prepare Kubernetes Cluster

If you don't have a Kubernetes cluster, you can set up a local one:

### Option A: Using k3s (Recommended for Linux)
```bash
# Install k3s
curl -sfL https://get.k3s.io | sh -

# Get kubeconfig
sudo cat /etc/rancher/k3s/k3s.yaml > ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
```

### Option B: Using minikube
```bash
# Install minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# Start minikube
minikube start --cpus=4 --memory=8192

# Get kubeconfig
minikube kubectl -- config view --raw > ~/.kube/config
```

### Option C: Using existing cluster
Ensure you have a valid kubeconfig file at `~/.kube/config`

## Step 2: Create GitHub Secrets

1. Go to your GitHub repository: https://github.com/ryanflavor/AegisTrader
2. Navigate to Settings → Secrets and variables → Actions
3. Click "New repository secret"

### Add KUBE_CONFIG Secret

1. Name: `KUBE_CONFIG`
2. Value: Base64 encoded kubeconfig

To get the base64 encoded value:
```bash
# Encode your kubeconfig
cat ~/.kube/config | base64 -w 0
```

Copy the output and paste it as the secret value.

## Step 3: Create Staging Environment in GitHub

1. Go to Settings → Environments
2. Click "New environment"
3. Name: `staging`
4. Configure protection rules (optional):
   - Required reviewers
   - Deployment branches: Restrict to `main`
   - Environment secrets (if different from repository secrets)

## Step 4: Prepare Staging Namespace

Create the staging namespace in your Kubernetes cluster:

```bash
kubectl create namespace aegis-staging
```

## Step 5: Install NATS in Staging

The CI/CD pipeline expects NATS to be running. Install it:

```bash
# Add NATS Helm repository
helm repo add nats https://nats-io.github.io/k8s/helm/charts/
helm repo update

# Install NATS in staging namespace
helm install nats nats/nats \
  --namespace aegis-staging \
  --set cluster.enabled=true \
  --set cluster.replicas=3 \
  --set nats.jetstream.enabled=true \
  --set nats.jetstream.memStorage.enabled=true \
  --set nats.jetstream.memStorage.size=1Gi
```

## Step 6: Configure Load Balancer (Optional)

If your cluster doesn't have a load balancer (common in local setups), install MetalLB:

```bash
# Install MetalLB
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.12/config/manifests/metallb-native.yaml

# Wait for MetalLB to be ready
kubectl wait --namespace metallb-system \
  --for=condition=ready pod \
  --selector=app=metallb \
  --timeout=90s

# Configure IP address pool (adjust IP range for your network)
cat <<EOF | kubectl apply -f -
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
  - 192.168.1.240-192.168.1.250  # Adjust this range
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default
  namespace: metallb-system
EOF
```

## Step 7: Test the Setup

1. Push a commit to the main branch
2. Check GitHub Actions: https://github.com/ryanflavor/AegisTrader/actions
3. The "Deploy to Staging" job should now run

## Step 8: Access Deployed Services

After successful deployment:

```bash
# Get services
kubectl get svc -n aegis-staging

# Port-forward to access services locally
kubectl port-forward -n aegis-staging svc/monitor-api 8100:8100
kubectl port-forward -n aegis-staging svc/monitor-ui 3100:3100
```

## Troubleshooting

### KUBE_CONFIG Secret Issues
- Ensure the kubeconfig is base64 encoded
- Test the kubeconfig locally first
- Check if the cluster is accessible from GitHub Actions

### Deployment Failures
- Check namespace exists: `kubectl get ns aegis-staging`
- Check NATS is running: `kubectl get pods -n aegis-staging | grep nats`
- Review deployment logs: `kubectl logs -n aegis-staging -l app=monitor-api`

### Load Balancer Issues
- For local clusters, ensure MetalLB is configured
- For cloud clusters, ensure your account has permissions to create load balancers

## Security Considerations

1. **Kubeconfig Security**:
   - Use a service account with limited permissions
   - Rotate credentials regularly
   - Consider using OIDC for authentication

2. **Network Security**:
   - Restrict cluster access to GitHub Actions IP ranges
   - Use network policies to isolate staging namespace

3. **Secret Management**:
   - Use Kubernetes secrets for sensitive data
   - Consider using sealed-secrets or external secret operators

## Next Steps

1. Set up monitoring (Prometheus/Grafana)
2. Configure ingress for external access
3. Set up production environment with stricter controls
4. Implement GitOps with ArgoCD or Flux
