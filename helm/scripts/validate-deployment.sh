#!/bin/bash
# Deployment validation script for AegisTrader Helm charts
# This script validates that all components are properly deployed and functional

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

# Default values
NAMESPACE="${NAMESPACE:-aegis-trader}"
RELEASE_NAME="${RELEASE_NAME:-aegis-trader}"
TIMEOUT="${TIMEOUT:-${DEPLOYMENT_TIMEOUT:-300}}"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is not installed"
        return 1
    fi
}

wait_for_pod() {
    local label=$1
    local expected_count=$2
    local timeout=$3

    log_info "Waiting for $expected_count pod(s) with label $label..."

    if kubectl wait --for=condition=ready pod \
        -l "$label" \
        -n "$NAMESPACE" \
        --timeout="${timeout}s" 2>/dev/null; then

        local actual_count
        actual_count=$(kubectl get pods -l "$label" -n "$NAMESPACE" --no-headers | wc -l)
        if [ "$actual_count" -eq "$expected_count" ]; then
            log_info "✓ $expected_count pod(s) ready"
            return 0
        else
            log_error "Expected $expected_count pods, found $actual_count"
            return 1
        fi
    else
        log_error "Pods not ready within ${timeout}s"
        return 1
    fi
}

check_service_endpoint() {
    local service=$1
    local port=$2

    log_info "Checking service $service on port $port..."

    if kubectl get service "$service" -n "$NAMESPACE" &>/dev/null; then
        local endpoints
        endpoints=$(kubectl get endpoints "$service" -n "$NAMESPACE" -o json | \
            jq -r '.subsets[0].addresses | length' 2>/dev/null || echo "0")

        if [ "$endpoints" -gt 0 ]; then
            log_info "✓ Service $service has $endpoints endpoint(s)"
            return 0
        else
            log_error "Service $service has no endpoints"
            return 1
        fi
    else
        log_error "Service $service not found"
        return 1
    fi
}

test_nats_connectivity() {
    log_info "Testing NATS connectivity..."

    local test_pod
    test_pod="nats-test-$(date +%s)"

    # Create test pod
    kubectl run "$test_pod" \
        --image=nats:alpine \
        --restart=Never \
        -n "$NAMESPACE" \
        --command -- sleep 300 &>/dev/null

    # Wait for pod to be ready
    kubectl wait --for=condition=ready pod "$test_pod" -n "$NAMESPACE" --timeout=60s &>/dev/null

    # Test NATS connection
    if kubectl exec "$test_pod" -n "$NAMESPACE" -- \
        nats server check connection --server="nats://${RELEASE_NAME}-nats:4222" &>/dev/null; then
        log_info "✓ NATS connection successful"

        # Test JetStream
        if kubectl exec "$test_pod" -n "$NAMESPACE" -- \
            nats server check jetstream --server="nats://${RELEASE_NAME}-nats:4222" &>/dev/null; then
            log_info "✓ JetStream enabled"

            # Check KV bucket
            if kubectl exec "$test_pod" -n "$NAMESPACE" -- \
                nats kv ls --server="nats://${RELEASE_NAME}-nats:4222" 2>/dev/null | grep -q "service-registry"; then
                log_info "✓ KV bucket 'service-registry' exists"
            else
                log_warn "KV bucket 'service-registry' not found (might not be created yet)"
            fi
        else
            log_error "JetStream not enabled"
        fi
    else
        log_error "NATS connection failed"
    fi

    # Cleanup
    kubectl delete pod "$test_pod" -n "$NAMESPACE" --force &>/dev/null
}

test_api_health() {
    log_info "Testing Management API health..."

    local api_pod
    api_pod=$(kubectl get pod -l "app.kubernetes.io/name=monitor-api" -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -n "$api_pod" ]; then
        if kubectl exec "$api_pod" -n "$NAMESPACE" -- wget -qO- http://localhost:8100/health &>/dev/null; then
            log_info "✓ API health check passed"
        else
            log_error "API health check failed"
        fi
    else
        log_error "No API pod found"
    fi
}

test_ui_accessibility() {
    log_info "Testing Monitor UI accessibility..."

    local ui_pod
    ui_pod=$(kubectl get pod -l "app.kubernetes.io/name=monitor-ui" -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -n "$ui_pod" ]; then
        if kubectl exec "$ui_pod" -n "$NAMESPACE" -- wget -qO- http://localhost:3100 2>/dev/null | grep -q "<html"; then
            log_info "✓ UI is serving content"
        else
            log_error "UI content check failed"
        fi
    else
        log_error "No UI pod found"
    fi
}

# Main validation flow
main() {
    echo "=== AegisTrader Deployment Validation ==="
    echo "Namespace: $NAMESPACE"
    echo "Release: $RELEASE_NAME"
    echo ""

    # Check prerequisites
    log_info "Checking prerequisites..."
    check_command kubectl || exit 1
    check_command jq || log_warn "jq not found, some checks will be limited"

    # Check namespace
    if ! kubectl get namespace "$NAMESPACE" &>/dev/null; then
        log_error "Namespace $NAMESPACE not found"
        exit 1
    fi

    # Validate deployments
    log_info "Validating deployments..."

    # Check NATS
    if wait_for_pod "app.kubernetes.io/name=nats" 3 "$TIMEOUT"; then
        check_service_endpoint "${RELEASE_NAME}-nats" 4222
        test_nats_connectivity
    fi

    # Check Management API
    if wait_for_pod "app.kubernetes.io/name=monitor-api" 1 "$TIMEOUT"; then
        check_service_endpoint "${RELEASE_NAME}-monitor-api" 8100
        test_api_health
    fi

    # Check Monitor UI
    if wait_for_pod "app.kubernetes.io/name=monitor-ui" 1 "$TIMEOUT"; then
        check_service_endpoint "${RELEASE_NAME}-monitor-ui" 3100
        test_ui_accessibility
    fi

    # Check persistent volumes
    log_info "Checking persistent volumes..."
    local pvcs
    pvcs=$(kubectl get pvc -n "$NAMESPACE" --no-headers | wc -l)
    if [ "$pvcs" -gt 0 ]; then
        log_info "✓ Found $pvcs PVC(s)"
        kubectl get pvc -n "$NAMESPACE"
    else
        log_warn "No PVCs found (might be using emptyDir for development)"
    fi

    # Summary
    echo ""
    echo "=== Validation Summary ==="

    local failed_pods
    failed_pods=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase!=Running,status.phase!=Succeeded --no-headers | wc -l)
    if [ "$failed_pods" -eq 0 ]; then
        log_info "All pods are healthy"
        echo ""
        echo "Deployment validation completed successfully! ✓"

        # Show access instructions
        echo ""
        echo "To access the services:"
        echo "  kubectl port-forward -n $NAMESPACE svc/${RELEASE_NAME}-monitor-ui 3100:3100"
        echo "  kubectl port-forward -n $NAMESPACE svc/${RELEASE_NAME}-monitor-api 8100:8100"
    else
        log_error "$failed_pods pod(s) are not healthy"
        kubectl get pods -n "$NAMESPACE" --field-selector=status.phase!=Running,status.phase!=Succeeded
        exit 1
    fi
}

# Run main function
main "$@"
