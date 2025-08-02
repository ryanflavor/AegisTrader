#!/bin/bash

# Script to help set up GitHub secrets for staging deployment

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}GitHub Staging Secret Setup${NC}"
echo "============================"

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh) is not installed${NC}"
    echo "Install it from: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${YELLOW}Not authenticated with GitHub. Running 'gh auth login'...${NC}"
    gh auth login
fi

# Get repository info
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo -e "Repository: ${GREEN}$REPO${NC}"

# Check for kubeconfig
KUBECONFIG_PATH="${KUBECONFIG:-$HOME/.kube/config}"
if [ ! -f "$KUBECONFIG_PATH" ]; then
    echo -e "${RED}Error: kubeconfig not found at $KUBECONFIG_PATH${NC}"
    echo "Please ensure you have a Kubernetes cluster configured"
    exit 1
fi

echo -e "\n${YELLOW}Current Kubernetes context:${NC}"
kubectl config current-context

echo -e "\n${YELLOW}This will create/update the KUBE_CONFIG secret in your GitHub repository.${NC}"
echo -e "${YELLOW}The secret will contain your current kubeconfig file.${NC}"
read -p "Continue? (y/N) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Create a temporary kubeconfig with only the current context
TEMP_KUBECONFIG=$(mktemp)
trap 'rm -f $TEMP_KUBECONFIG' EXIT

# Export current context to temporary file
kubectl config view --minify --flatten > "$TEMP_KUBECONFIG"

# Base64 encode the kubeconfig
ENCODED_CONFIG=$(cat "$TEMP_KUBECONFIG" | base64 -w 0)

# Set the secret
echo -e "\n${YELLOW}Setting KUBE_CONFIG secret...${NC}"
echo "$ENCODED_CONFIG" | gh secret set KUBE_CONFIG

echo -e "${GREEN}✓ KUBE_CONFIG secret has been set${NC}"

# Create staging environment if it doesn't exist
echo -e "\n${YELLOW}Checking GitHub environment...${NC}"
if ! gh api repos/$REPO/environments/staging &> /dev/null; then
    echo "Creating 'staging' environment..."
    gh api repos/$REPO/environments/staging -X PUT \
        --field "deployment_branch_policy[protected_branches]=false" \
        --field "deployment_branch_policy[custom_branch_policies]=true" || true
fi

echo -e "${GREEN}✓ Staging environment is configured${NC}"

# Display next steps
echo -e "\n${GREEN}Setup Complete!${NC}"
echo "==============="
echo -e "\nNext steps:"
echo "1. Push a commit to the main branch"
echo "2. Check GitHub Actions at: https://github.com/$REPO/actions"
echo "3. The 'Deploy to Staging' job should now run successfully"
echo ""
echo "To test locally first:"
echo "  make deploy-local-staging"
echo ""
echo "To manually trigger staging deployment:"
echo "  gh workflow run 'CI/CD Pipeline (Local Staging)'"
