#!/bin/bash
# Quick setup script for CI/CD

echo "🚀 AegisTrader CI/CD Setup"
echo "========================="
echo ""

# Check if kubectl is configured
if ! kubectl cluster-info &>/dev/null; then
    echo "❌ kubectl is not configured or cluster is not accessible"
    echo "Please configure kubectl first"
    exit 1
fi

echo "✅ Kubernetes cluster is accessible"
echo ""

# Apply RBAC
echo "📦 Applying RBAC configuration..."
kubectl apply -f k8s/ci-rbac.yaml

# Generate kubeconfig
echo ""
echo "🔑 Generating CI/CD kubeconfig..."
cd scripts
./generate-ci-kubeconfig.sh
cd ..

echo ""
echo "📋 Setup Instructions:"
echo "====================="
echo ""
echo "1. Go to your GitHub repository: https://github.com/realAnthony/AegisTrader"
echo "2. Navigate to: Settings → Secrets and variables → Actions"
echo "3. Click 'New repository secret'"
echo "4. Add the following secret:"
echo "   - Name: KUBE_CONFIG"
echo "   - Value: Copy content from scripts/ci-kubeconfig.b64"
echo ""
echo "5. (Optional) Set up environments:"
echo "   - Go to Settings → Environments"
echo "   - Create 'staging' environment"
echo "   - Add any environment-specific configuration"
echo ""
echo "✅ Once complete, your CI/CD pipeline will be ready to deploy!"
