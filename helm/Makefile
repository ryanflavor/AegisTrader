# AegisTrader Helm Deployment Makefile
SHELL := /bin/bash

# Default values
NAMESPACE ?= aegis-trader
RELEASE_NAME ?= aegis-trader
VALUES_FILE ?= values.yaml
HELM_TIMEOUT ?= 10m

# Helm command
HELM := helm

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

.PHONY: help
help: ## Show this help message
	@echo 'Usage: make [target] [NAMESPACE=namespace] [VALUES_FILE=values.yaml]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ''
	@echo 'Examples:'
	@echo '  make install                    # Install with default values'
	@echo '  make install VALUES_FILE=values.dev.yaml  # Install with dev values'
	@echo '  make install NAMESPACE=dev      # Install in dev namespace'

.PHONY: check-tools
check-tools: ## Check required tools are installed
	@echo "$(YELLOW)Checking required tools...$(NC)"
	@which kubectl > /dev/null || (echo "$(RED)kubectl not found$(NC)" && exit 1)
	@which helm > /dev/null || (echo "$(RED)helm not found$(NC)" && exit 1)
	@echo "$(GREEN)All required tools found$(NC)"

.PHONY: create-namespace
create-namespace: ## Create namespace if it doesn't exist
	@echo "$(YELLOW)Creating namespace $(NAMESPACE)...$(NC)"
	@kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	@kubectl label namespace $(NAMESPACE) app.kubernetes.io/name=aegis-trader --overwrite
	@echo "$(GREEN)Namespace ready$(NC)"

.PHONY: helm-deps
helm-deps: ## Update Helm dependencies
	@echo "$(YELLOW)Updating Helm dependencies...$(NC)"
	@$(HELM) repo add nats $${NATS_HELM_REPO:-https://nats-io.github.io/k8s/helm/charts/} || true
	@$(HELM) repo update
	@$(HELM) dependency update .
	@echo "$(GREEN)Dependencies updated$(NC)"

.PHONY: lint
lint: ## Run Helm lint
	@echo "$(YELLOW)Linting Helm charts...$(NC)"
	@$(HELM) lint . -f $(VALUES_FILE)
	@$(HELM) lint ./charts/monitor-api
	@$(HELM) lint ./charts/monitor-ui
	@echo "$(GREEN)Lint passed$(NC)"

.PHONY: template
template: ## Generate and display Kubernetes manifests
	@echo "$(YELLOW)Generating templates...$(NC)"
	@$(HELM) template $(RELEASE_NAME) . -f $(VALUES_FILE) --namespace $(NAMESPACE)

.PHONY: install
install: check-tools create-namespace helm-deps lint ## Install the complete stack
	@echo "$(YELLOW)Installing AegisTrader...$(NC)"
	@$(HELM) install $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--values $(VALUES_FILE) \
		--timeout $(HELM_TIMEOUT) \
		--wait \
		--debug
	@echo "$(GREEN)Installation complete!$(NC)"
	@echo ""
	@$(HELM) status $(RELEASE_NAME) --namespace $(NAMESPACE)

.PHONY: upgrade
upgrade: check-tools helm-deps lint ## Upgrade existing installation
	@echo "$(YELLOW)Upgrading AegisTrader...$(NC)"
	@$(HELM) upgrade $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--values $(VALUES_FILE) \
		--timeout $(HELM_TIMEOUT) \
		--wait \
		--debug
	@echo "$(GREEN)Upgrade complete!$(NC)"

.PHONY: test
test: ## Run Helm tests
	@echo "$(YELLOW)Running Helm tests...$(NC)"
	@$(HELM) test $(RELEASE_NAME) --namespace $(NAMESPACE) --timeout 5m || true
	@echo "$(GREEN)Tests complete!$(NC)"

.PHONY: validate
validate: ## Validate deployment (works with or without K8s)
	@echo "$(YELLOW)Validating deployment...$(NC)"
	@cd $(dir $(MAKEFILE_LIST)) && ./test-deployment.sh
	@echo "$(GREEN)Validation complete!$(NC)"

.PHONY: status
status: ## Check deployment status
	@echo "$(YELLOW)Checking deployment status...$(NC)"
	@$(HELM) status $(RELEASE_NAME) --namespace $(NAMESPACE)
	@echo ""
	@echo "$(YELLOW)Pods:$(NC)"
	@kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/instance=$(RELEASE_NAME)
	@echo ""
	@echo "$(YELLOW)Services:$(NC)"
	@kubectl get svc -n $(NAMESPACE) -l app.kubernetes.io/instance=$(RELEASE_NAME)

.PHONY: logs
logs: ## Show logs from all pods
	@echo "$(YELLOW)Fetching logs...$(NC)"
	@kubectl logs -n $(NAMESPACE) -l app.kubernetes.io/instance=$(RELEASE_NAME) --all-containers=true --prefix=true -f

.PHONY: port-forward
port-forward: ## Port forward to access services locally
	@echo "$(YELLOW)Setting up port forwarding...$(NC)"
	@echo "UI will be available at http://localhost:$${UI_PORT:-3100}"
	@echo "API will be available at http://localhost:$${API_PORT:-8100}"
	@echo "Press Ctrl+C to stop"
	@kubectl port-forward -n $(NAMESPACE) svc/$(RELEASE_NAME)-monitor-ui $${UI_PORT:-3100}:$${UI_PORT:-3100} &
	@kubectl port-forward -n $(NAMESPACE) svc/$(RELEASE_NAME)-monitor-api $${API_PORT:-8100}:$${API_PORT:-8100}

.PHONY: uninstall
uninstall: check-tools ## Uninstall the stack
	@echo "$(YELLOW)Uninstalling AegisTrader...$(NC)"
	@$(HELM) uninstall $(RELEASE_NAME) --namespace $(NAMESPACE)
	@echo "$(GREEN)Uninstall complete!$(NC)"

.PHONY: clean
clean: uninstall ## Clean up everything including namespace
	@echo "$(YELLOW)Cleaning up namespace...$(NC)"
	@kubectl delete namespace $(NAMESPACE) --ignore-not-found=true
	@echo "$(GREEN)Cleanup complete!$(NC)"

.PHONY: dry-run
dry-run: check-tools create-namespace helm-deps lint ## Perform a dry-run installation
	@echo "$(YELLOW)Performing dry-run installation...$(NC)"
	@$(HELM) install $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--values $(VALUES_FILE) \
		--dry-run \
		--debug

# Development helpers
.PHONY: dev-install
dev-install: ## Install with development values
	@$(MAKE) install VALUES_FILE=values.dev.yaml NAMESPACE=aegis-dev

.PHONY: dev-upgrade
dev-upgrade: ## Upgrade with development values
	@$(MAKE) upgrade VALUES_FILE=values.dev.yaml NAMESPACE=aegis-dev

.PHONY: dev-uninstall
dev-uninstall: ## Uninstall development deployment
	@$(MAKE) uninstall NAMESPACE=aegis-dev