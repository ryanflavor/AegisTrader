#!/bin/bash

# Setup K8s Development Environment for AegisSDK
# This script sets up the local K8s environment for AegisSDK development

set -e

NAMESPACE="aegis-trader"
NATS_SERVICE="aegis-trader-nats"
NATS_PORT=4222
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "====================================="
echo "AegisSDK K8s Development Setup"
echo "====================================="

# Function to check command availability
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}✗ $1 is not installed${NC}"
        echo "  Please install $1 first"
        exit 1
    else
        echo -e "${GREEN}✓ $1 is available${NC}"
    fi
}

# Function to check K8s connectivity
check_k8s() {
    echo -e "\n${YELLOW}Checking Kubernetes connectivity...${NC}"
    if kubectl cluster-info &> /dev/null; then
        echo -e "${GREEN}✓ Connected to Kubernetes cluster${NC}"
        CONTEXT=$(kubectl config current-context)
        echo "  Current context: $CONTEXT"
    else
        echo -e "${RED}✗ Cannot connect to Kubernetes cluster${NC}"
        echo "  Please ensure kubectl is configured correctly"
        exit 1
    fi
}

# Function to create namespace
create_namespace() {
    echo -e "\n${YELLOW}Checking namespace $NAMESPACE...${NC}"
    if kubectl get namespace $NAMESPACE &> /dev/null; then
        echo -e "${GREEN}✓ Namespace $NAMESPACE exists${NC}"
    else
        echo "  Creating namespace $NAMESPACE..."
        kubectl create namespace $NAMESPACE
        echo -e "${GREEN}✓ Namespace $NAMESPACE created${NC}"
    fi
}

# Function to check NATS deployment
check_nats() {
    echo -e "\n${YELLOW}Checking NATS deployment...${NC}"

    # Check if NATS service exists
    if kubectl get service $NATS_SERVICE -n $NAMESPACE &> /dev/null; then
        echo -e "${GREEN}✓ NATS service found${NC}"

        # Check if NATS pods are running
        NATS_PODS=$(kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=nats --no-headers 2>/dev/null | wc -l)
        if [ "$NATS_PODS" -gt 0 ]; then
            echo -e "${GREEN}✓ NATS pods are running${NC}"
            kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=nats
        else
            echo -e "${YELLOW}⚠ No NATS pods found${NC}"
            echo "  You may need to deploy NATS using Helm:"
            echo "  helm install $NATS_SERVICE nats/nats -n $NAMESPACE --set jetstream.enabled=true"
        fi
    else
        echo -e "${RED}✗ NATS service not found${NC}"
        echo ""
        echo "To deploy NATS, run:"
        echo "  helm repo add nats https://nats-io.github.io/k8s/helm/charts/"
        echo "  helm install $NATS_SERVICE nats/nats -n $NAMESPACE --set jetstream.enabled=true"
        exit 1
    fi
}

# Function to setup port forwarding
setup_port_forward() {
    echo -e "\n${YELLOW}Setting up port forwarding...${NC}"

    # Check if port forwarding is already active
    if lsof -i :$NATS_PORT &> /dev/null; then
        echo -e "${YELLOW}⚠ Port $NATS_PORT is already in use${NC}"

        # Check if it's kubectl port-forward
        if ps aux | grep -q "[k]ubectl port-forward.*$NATS_PORT"; then
            echo -e "${GREEN}✓ Port forwarding appears to be active${NC}"
        else
            echo -e "${RED}✗ Port $NATS_PORT is used by another process${NC}"
            echo "  Please free up port $NATS_PORT or stop the existing process"
            exit 1
        fi
    else
        echo "Starting port forwarding to NATS..."
        kubectl port-forward -n $NAMESPACE svc/$NATS_SERVICE $NATS_PORT:$NATS_PORT &
        PF_PID=$!

        # Wait for port forwarding to be ready
        sleep 3

        if ps -p $PF_PID > /dev/null; then
            echo -e "${GREEN}✓ Port forwarding started (PID: $PF_PID)${NC}"
            echo "  NATS is now accessible at: nats://localhost:$NATS_PORT"
            echo ""
            echo "To stop port forwarding later, run:"
            echo "  kill $PF_PID"
        else
            echo -e "${RED}✗ Failed to start port forwarding${NC}"
            exit 1
        fi
    fi
}

# Function to test NATS connectivity
test_nats_connection() {
    echo -e "\n${YELLOW}Testing NATS connectivity...${NC}"

    # Try to connect using nc if available
    if command -v nc &> /dev/null; then
        if nc -zv localhost $NATS_PORT 2>&1 | grep -q succeeded; then
            echo -e "${GREEN}✓ NATS is reachable on localhost:$NATS_PORT${NC}"
        else
            echo -e "${RED}✗ Cannot connect to NATS on localhost:$NATS_PORT${NC}"
        fi
    else
        echo "  Skipping connection test (nc not available)"
    fi
}

# Function to create test KV bucket
setup_kv_bucket() {
    echo -e "\n${YELLOW}Setting up NATS KV bucket...${NC}"

    # Check if nats CLI is available
    if command -v nats &> /dev/null; then
        # Check if service_registry bucket exists
        if nats kv ls 2>/dev/null | grep -q service_registry; then
            echo -e "${GREEN}✓ KV bucket 'service_registry' exists${NC}"
        else
            echo "  Creating KV bucket 'service_registry'..."
            nats kv add service_registry --replicas=1 --ttl=30s
            echo -e "${GREEN}✓ KV bucket 'service_registry' created${NC}"
        fi
    else
        echo "  NATS CLI not available - skipping KV bucket setup"
        echo "  Install NATS CLI for full functionality:"
        echo "  https://github.com/nats-io/natscli"
    fi
}

# Function to display environment info
display_info() {
    echo ""
    echo "====================================="
    echo "Environment Setup Complete!"
    echo "====================================="
    echo ""
    echo "Configuration:"
    echo "  Namespace:     $NAMESPACE"
    echo "  NATS Service:  $NATS_SERVICE"
    echo "  NATS URL:      nats://localhost:$NATS_PORT"
    echo ""
    echo "Quick Test Commands:"
    echo "  # Test with Python SDK"
    echo "  python -c \"from aegis_sdk.developer import quick_setup; import asyncio; asyncio.run(quick_setup('test-service'))\""
    echo ""
    echo "  # Run example service"
    echo "  python packages/aegis-sdk/aegis_sdk/examples/quickstart/echo_service.py"
    echo ""
    echo "  # Run configuration validator"
    echo "  python packages/aegis-sdk/aegis_sdk/developer/config_validator.py"
    echo ""
    echo "Useful Commands:"
    echo "  # Watch services"
    echo "  kubectl get pods -n $NAMESPACE -w"
    echo ""
    echo "  # Check logs"
    echo "  kubectl logs -n $NAMESPACE <pod-name>"
    echo ""
    echo "  # Shell into NATS box"
    echo "  kubectl exec -it -n $NAMESPACE ${NATS_SERVICE}-box -- sh"
}

# Main execution
main() {
    echo "Checking prerequisites..."
    check_command kubectl
    check_command python3

    check_k8s
    create_namespace
    check_nats
    setup_port_forward
    test_nats_connection
    setup_kv_bucket
    display_info
}

# Run main function
main
