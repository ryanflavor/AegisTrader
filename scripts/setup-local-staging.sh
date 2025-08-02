#!/bin/bash

# Local Staging Environment Setup Script
# This script sets up a local staging environment for AegisTrader

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="aegis-staging"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}AegisTrader Local Staging Setup${NC}"
echo "=================================="

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to wait for pod to be ready
wait_for_pod() {
    local label=$1
    local namespace=$2
    echo -n "Waiting for pods with label $label to be ready..."
    kubectl wait --for=condition=ready pod -l "$label" -n "$namespace" --timeout=300s
    echo -e " ${GREEN}✓${NC}"
}

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

if ! command_exists kubectl; then
    echo -e "${RED}Error: kubectl is not installed${NC}"
    exit 1
fi

if ! command_exists helm; then
    echo -e "${RED}Error: helm is not installed${NC}"
    exit 1
fi

if ! command_exists docker; then
    echo -e "${RED}Error: docker is not installed${NC}"
    exit 1
fi

# Check Kubernetes cluster
echo -n "Checking Kubernetes cluster..."
if kubectl cluster-info &>/dev/null; then
    echo -e " ${GREEN}✓${NC}"
    kubectl cluster-info | head -n 1
else
    echo -e " ${RED}✗${NC}"
    echo -e "${RED}Error: No Kubernetes cluster found${NC}"
    echo -e "${YELLOW}Please set up a local cluster using one of:${NC}"
    echo "  - k3s: curl -sfL https://get.k3s.io | sh -"
    echo "  - minikube: minikube start"
    echo "  - kind: kind create cluster"
    exit 1
fi

# Create namespace
echo -e "\n${YELLOW}Setting up namespace...${NC}"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# Add Helm repositories
echo -e "\n${YELLOW}Adding Helm repositories...${NC}"
helm repo add nats https://nats-io.github.io/k8s/helm/charts/
helm repo update

# Deploy NATS
echo -e "\n${YELLOW}Deploying NATS...${NC}"
helm upgrade --install nats nats/nats \
    --namespace "$NAMESPACE" \
    --set cluster.enabled=true \
    --set cluster.replicas=1 \
    --set nats.jetstream.enabled=true \
    --set nats.jetstream.memStorage.enabled=true \
    --set nats.jetstream.memStorage.size=256Mi \
    --set nats.resources.requests.memory=256Mi \
    --set nats.resources.limits.memory=512Mi \
    --wait

wait_for_pod "app.kubernetes.io/name=nats" "$NAMESPACE"

# Build Docker images
echo -e "\n${YELLOW}Building Docker images...${NC}"
cd "$PROJECT_ROOT"

echo "Building monitor-api..."
docker build -t aegis/monitor-api:local -f apps/monitor-api/Dockerfile .

echo "Building monitor-ui..."
docker build -t aegis/monitor-ui:local -f apps/monitor-ui/Dockerfile .

# Load images into cluster (for kind/minikube)
if command_exists kind; then
    echo -e "\n${YELLOW}Loading images into kind cluster...${NC}"
    kind load docker-image aegis/monitor-api:local aegis/monitor-ui:local 2>/dev/null || true
elif command_exists minikube; then
    echo -e "\n${YELLOW}Loading images into minikube...${NC}"
    minikube image load aegis/monitor-api:local aegis/monitor-ui:local 2>/dev/null || true
fi

# Deploy AegisTrader services
echo -e "\n${YELLOW}Deploying AegisTrader services...${NC}"
cd "$PROJECT_ROOT/helm"

# Generate values file for local deployment
cat > values.staging.yaml << EOF
global:
  imageRegistry: ""
  imageTag: "local"
  imagePullPolicy: Never

monitor-api:
  image:
    repository: aegis/monitor-api
  service:
    type: ClusterIP
  resources:
    requests:
      memory: "128Mi"
      cpu: "100m"
    limits:
      memory: "256Mi"
      cpu: "500m"

monitor-ui:
  image:
    repository: aegis/monitor-ui
  service:
    type: ClusterIP
  resources:
    requests:
      memory: "64Mi"
      cpu: "50m"
    limits:
      memory: "128Mi"
      cpu: "200m"

nats:
  enabled: false  # Using external NATS
EOF

helm upgrade --install aegis . \
    --namespace "$NAMESPACE" \
    --values values.staging.yaml \
    --wait

# Wait for services to be ready
wait_for_pod "app.kubernetes.io/name=monitor-api" "$NAMESPACE"
wait_for_pod "app.kubernetes.io/name=monitor-ui" "$NAMESPACE"

# Set up port forwarding
echo -e "\n${YELLOW}Setting up port forwarding...${NC}"

# Kill any existing port-forward processes
pkill -f "kubectl port-forward.*$NAMESPACE" || true
sleep 2

# Start port forwarding in background
kubectl port-forward -n "$NAMESPACE" svc/monitor-api 8100:8100 >/dev/null 2>&1 &
PF_API=$!
kubectl port-forward -n "$NAMESPACE" svc/monitor-ui 3100:3100 >/dev/null 2>&1 &
PF_UI=$!
kubectl port-forward -n "$NAMESPACE" svc/nats 4222:4222 >/dev/null 2>&1 &
PF_NATS=$!

# Give port-forwarding time to establish
sleep 3

# Verify deployment
echo -e "\n${YELLOW}Verifying deployment...${NC}"

echo -n "Testing Monitor API health..."
if curl -s http://localhost:8100/health | grep -q "healthy"; then
    echo -e " ${GREEN}✓${NC}"
else
    echo -e " ${RED}✗${NC}"
fi

echo -n "Testing Monitor UI..."
if curl -s http://localhost:3100 | grep -q "<title>"; then
    echo -e " ${GREEN}✓${NC}"
else
    echo -e " ${RED}✗${NC}"
fi

echo -n "Testing NATS connection..."
if nc -zv localhost 4222 2>&1 | grep -q succeeded; then
    echo -e " ${GREEN}✓${NC}"
else
    echo -e " ${RED}✗${NC}"
fi

# Display summary
echo -e "\n${GREEN}Local Staging Environment Ready!${NC}"
echo "=================================="
echo -e "Monitor API: ${GREEN}http://localhost:8100${NC}"
echo -e "Monitor UI:  ${GREEN}http://localhost:3100${NC}"
echo -e "NATS:        ${GREEN}localhost:4222${NC}"
echo ""
echo "Port forwarding PIDs:"
echo "  API: $PF_API"
echo "  UI:  $PF_UI"
echo "  NATS: $PF_NATS"
echo ""
echo "To stop port forwarding:"
echo "  kill $PF_API $PF_UI $PF_NATS"
echo ""
echo "To clean up:"
echo "  helm uninstall aegis -n $NAMESPACE"
echo "  helm uninstall nats -n $NAMESPACE"
echo "  kubectl delete namespace $NAMESPACE"
echo ""
echo -e "${YELLOW}Note: Keep this terminal open to maintain port forwarding${NC}"

# Keep script running to maintain port forwarding
echo -e "\n${YELLOW}Press Ctrl+C to stop port forwarding and exit${NC}"
trap 'kill $PF_API $PF_UI $PF_NATS 2>/dev/null; exit' INT
wait
