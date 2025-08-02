# GitHub Actions CI/CD Setup Guide

## Required GitHub Secrets

To enable the CI/CD pipeline, you need to configure the following secrets in your GitHub repository:

### 1. KUBE_CONFIG

This secret contains the base64-encoded kubeconfig file for accessing your Kubernetes cluster.

#### Steps to create KUBE_CONFIG secret:

1. **Get your kubeconfig file:**
   ```bash
   # If using a local cluster
   cat ~/.kube/config

   # If using a specific kubeconfig
   cat /path/to/your/kubeconfig
   ```

2. **Base64 encode the kubeconfig:**
   ```bash
   # On Linux/Mac
   base64 -w 0 ~/.kube/config > kubeconfig.b64

   # On Mac (alternative)
   base64 -i ~/.kube/config -o kubeconfig.b64
   ```

3. **Add to GitHub Secrets:**
   - Go to your repository on GitHub
   - Navigate to Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `KUBE_CONFIG`
   - Value: Copy the content of `kubeconfig.b64`
   - Click "Add secret"

### 2. Environment-specific Configuration

The pipeline uses different environments:
- `staging`: For staging deployments (automatic on main branch)
- `production`: For production deployments (manual approval required)

#### Setting up Environment Secrets:

1. Go to Settings → Environments
2. Create `staging` environment
3. Add any environment-specific secrets or variables

## Troubleshooting

### Connection Refused Error

If you see errors like:
```
The connection to the server localhost:8080 was refused
```

This indicates that:
1. The KUBE_CONFIG secret is not set or is empty
2. The kubeconfig is invalid or expired
3. The cluster is not accessible from GitHub Actions

### Verification Steps

1. **Test your kubeconfig locally:**
   ```bash
   export KUBECONFIG=/path/to/your/kubeconfig
   kubectl get nodes
   ```

2. **Check the kubeconfig server URL:**
   ```bash
   grep server ~/.kube/config
   ```
   Make sure the server URL is accessible from the internet if using GitHub-hosted runners.

3. **For private clusters:**
   - Consider using self-hosted runners within your network
   - Or use a VPN/bastion host setup
   - Or expose the API server with proper security

## Security Best Practices

1. **Limit kubeconfig permissions:**
   - Create a service account specifically for CI/CD
   - Grant only necessary permissions (namespace-scoped)
   - Rotate credentials regularly

2. **Example RBAC for CI/CD:**
   ```yaml
   apiVersion: v1
   kind: ServiceAccount
   metadata:
     name: github-actions
     namespace: aegis-staging
   ---
   apiVersion: rbac.authorization.k8s.io/v1
   kind: Role
   metadata:
     name: github-actions-deployer
     namespace: aegis-staging
   rules:
   - apiGroups: ["", "apps", "batch"]
     resources: ["*"]
     verbs: ["*"]
   ---
   apiVersion: rbac.authorization.k8s.io/v1
   kind: RoleBinding
   metadata:
     name: github-actions-deployer
     namespace: aegis-staging
   roleRef:
     apiGroup: rbac.authorization.k8s.io
     kind: Role
     name: github-actions-deployer
   subjects:
   - kind: ServiceAccount
     name: github-actions
     namespace: aegis-staging
   ```

3. **Generate kubeconfig for service account:**
   ```bash
   # Create a script to generate kubeconfig
   ./scripts/generate-ci-kubeconfig.sh
   ```

## Alternative Deployment Methods

If you cannot expose your Kubernetes API server:

1. **GitOps with ArgoCD:**
   - Push manifests to git
   - Let ArgoCD pull and deploy

2. **Self-hosted runners:**
   - Run GitHub Actions runners in your infrastructure
   - Direct access to cluster

3. **Webhook-based deployment:**
   - GitHub Actions triggers a webhook
   - Internal service handles deployment
