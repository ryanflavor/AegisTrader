#!/bin/bash
# Script to run sticky active K8s integration tests

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SDK_DIR="$SCRIPT_DIR/../../.."
NAMESPACE="aegis-sticky-test"

echo "=== Sticky Active K8s Integration Tests ==="

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl."
    exit 1
fi

# Check if we can connect to cluster
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster. Please ensure kubectl is configured."
    exit 1
fi

echo "✅ Connected to Kubernetes cluster"

# Check if NATS is running
if ! kubectl get svc aegis-trader-nats -n aegis-trader &> /dev/null; then
    echo "❌ NATS service not found in aegis-trader namespace."
    echo "   Please deploy NATS first using: make dev-update"
    exit 1
fi

echo "✅ NATS service found"

# Build the test image
echo "🔨 Building test Docker image..."
cd "$SDK_DIR"
docker build -f tests/integration/k8s/Dockerfile -t aegis-sdk-test:latest .

# Load image into Kind cluster (if using Kind)
if kubectl config current-context | grep -q "kind"; then
    echo "📦 Loading image into Kind cluster..."
    kind load docker-image aegis-sdk-test:latest --name aegis-local || true
fi

# Clean up any existing namespace
echo "🧹 Cleaning up existing resources..."
kubectl delete namespace $NAMESPACE --ignore-not-found=true --wait=false

# Apply the deployment
echo "🚀 Deploying sticky service test pods..."
kubectl apply -f "$SCRIPT_DIR/sticky-service-deployment.yaml"

# Wait for namespace to be ready
echo "⏳ Waiting for namespace to be ready..."
kubectl wait --for=condition=Active namespace/$NAMESPACE --timeout=30s || true

# Wait for pods to be ready
echo "⏳ Waiting for pods to be ready..."
kubectl wait --for=condition=Ready pod -l app=sticky-service -n $NAMESPACE --timeout=60s

# Show pod status
echo "📊 Pod status:"
kubectl get pods -n $NAMESPACE

# Check if port-forward is needed for tests
NATS_PORT_FORWARD_PID=""
if ! nc -z localhost 4222 2>/dev/null; then
    echo "🔌 Setting up NATS port forwarding..."
    kubectl port-forward -n aegis-trader svc/aegis-trader-nats 4222:4222 &
    NATS_PORT_FORWARD_PID=$!
    sleep 2
fi

# Run the integration tests
echo "🧪 Running integration tests..."
cd "$SDK_DIR"
python -m pytest tests/integration/test_sticky_active_k8s_integration.py -v -k k8s

TEST_RESULT=$?

# Show logs from pods
echo "📜 Pod logs:"
for pod in $(kubectl get pods -n $NAMESPACE -o name); do
    echo "--- Logs from $pod ---"
    kubectl logs -n $NAMESPACE $pod --tail=50
done

# Cleanup
echo "🧹 Cleaning up..."
kubectl delete namespace $NAMESPACE --ignore-not-found=true

# Kill port-forward if we started it
if [ ! -z "$NATS_PORT_FORWARD_PID" ]; then
    kill $NATS_PORT_FORWARD_PID 2>/dev/null || true
fi

if [ $TEST_RESULT -eq 0 ]; then
    echo "✅ All tests passed!"
else
    echo "❌ Some tests failed. Check the output above."
fi

exit $TEST_RESULT
