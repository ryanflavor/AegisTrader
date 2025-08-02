#!/bin/bash
# Script to generate kubeconfig for GitHub Actions CI/CD

set -e

NAMESPACE="aegis-staging"
SERVICE_ACCOUNT="github-actions"
CLUSTER_NAME="aegis-cluster"
KUBECONFIG_FILE="ci-kubeconfig"

echo "🔧 Generating kubeconfig for CI/CD..."

# Create service account if it doesn't exist
kubectl get serviceaccount ${SERVICE_ACCOUNT} -n ${NAMESPACE} &>/dev/null || {
    echo "Creating service account..."
    kubectl create serviceaccount ${SERVICE_ACCOUNT} -n ${NAMESPACE}
}

# Get the service account token secret name
SECRET_NAME=""
SECRET_NAME=$(kubectl get serviceaccount ${SERVICE_ACCOUNT} -n ${NAMESPACE} -o jsonpath='{.secrets[0].name}')

# If no secret exists (K8s 1.24+), create one
if [ -z "$SECRET_NAME" ]; then
    echo "Creating service account token..."
    kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: ${SERVICE_ACCOUNT}-token
  namespace: ${NAMESPACE}
  annotations:
    kubernetes.io/service-account.name: ${SERVICE_ACCOUNT}
type: kubernetes.io/service-account-token
EOF
    SECRET_NAME="${SERVICE_ACCOUNT}-token"
    # Wait for token to be populated
    sleep 2
fi

# Get the token
TOKEN=""
TOKEN=$(kubectl get secret ${SECRET_NAME} -n ${NAMESPACE} -o jsonpath='{.data.token}' | base64 -d)

# Get the certificate
CA_CERT=""
CA_CERT=$(kubectl get secret ${SECRET_NAME} -n ${NAMESPACE} -o jsonpath='{.data.ca\.crt}')

# Get the API server URL
API_SERVER=""
API_SERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')

# Create kubeconfig
cat > ${KUBECONFIG_FILE} <<EOF
apiVersion: v1
kind: Config
clusters:
- name: ${CLUSTER_NAME}
  cluster:
    server: ${API_SERVER}
    certificate-authority-data: ${CA_CERT}
contexts:
- name: ${SERVICE_ACCOUNT}@${CLUSTER_NAME}
  context:
    cluster: ${CLUSTER_NAME}
    namespace: ${NAMESPACE}
    user: ${SERVICE_ACCOUNT}
current-context: ${SERVICE_ACCOUNT}@${CLUSTER_NAME}
users:
- name: ${SERVICE_ACCOUNT}
  user:
    token: ${TOKEN}
EOF

echo "✅ Kubeconfig generated: ${KUBECONFIG_FILE}"

# Test the kubeconfig
echo "🧪 Testing kubeconfig..."
KUBECONFIG=${KUBECONFIG_FILE} kubectl get pods -n ${NAMESPACE} &>/dev/null && {
    echo "✅ Kubeconfig is valid"
} || {
    echo "❌ Kubeconfig test failed"
    exit 1
}

# Generate base64 encoded version
echo "📦 Generating base64 encoded version..."
base64 -w 0 ${KUBECONFIG_FILE} > ${KUBECONFIG_FILE}.b64

echo ""
echo "📋 Next steps:"
echo "1. Copy the content of ${KUBECONFIG_FILE}.b64"
echo "2. Add it as KUBE_CONFIG secret in GitHub repository settings"
echo ""
echo "⚠️  Security notes:"
echo "- This kubeconfig has full access to the ${NAMESPACE} namespace"
echo "- Store it securely and rotate regularly"
echo "- Consider using more restrictive RBAC if needed"
