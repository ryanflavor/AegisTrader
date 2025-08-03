#!/bin/bash
# Deploy AegisTrader with TTL support enabled

set -e

echo "=== Deploying AegisTrader with TTL Support ==="

# Check if we're in the helm directory
if [ ! -f "Chart.yaml" ]; then
  echo "ERROR: Must run from the helm directory"
  exit 1
fi

# Uninstall existing release if it exists
echo "1. Checking for existing installation..."
if helm list -n aegis-system | grep -q aegis-trader; then
  echo "   - Uninstalling existing release..."
  helm uninstall aegis-trader -n aegis-system
  echo "   - Waiting for resources to be cleaned up..."
  sleep 10
fi

# Create namespace if it doesn't exist
echo "2. Ensuring namespace exists..."
kubectl create namespace aegis-system --dry-run=client -o yaml | kubectl apply -f -

# Install with JetStream enabled
echo "3. Installing with JetStream configuration..."
helm install aegis-trader . \
  -n aegis-system \
  -f values.yaml \
  -f values.jetstream.yaml \
  --wait \
  --timeout 10m

# Wait for NATS to be ready
echo "4. Waiting for NATS pods to be ready..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=nats -n aegis-system --timeout=300s

# Check JetStream status
echo "5. Verifying JetStream is enabled..."
POD=$(kubectl get pod -n aegis-system -l app.kubernetes.io/name=nats -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n aegis-system $POD -- nats server report jetstream

# Check if KV bucket was created
echo "6. Checking KV bucket creation..."
kubectl logs -n aegis-system -l app.kubernetes.io/component=nats-kv-setup --tail=50

# Port forward for testing
echo "7. Setting up port forwarding..."
kubectl port-forward -n aegis-system svc/aegis-trader-nats 4222:4222 &
PF_PID=$!
echo "   Port forwarding PID: $PF_PID"

# Give port forwarding time to establish
sleep 5

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "NATS is available at: nats://localhost:4222"
echo "Port forwarding PID: $PF_PID"
echo ""
echo "To test TTL functionality:"
echo "  python test_ttl_k8s.py"
echo ""
echo "To stop port forwarding:"
echo "  kill $PF_PID"
echo ""
