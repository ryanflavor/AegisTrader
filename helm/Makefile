# Helm Refactored Makefile
HELM_RELEASE_NAME ?= aegis-trader
K8S_NAMESPACE ?= aegis-trader
VERSION ?= $(shell date +%Y%m%d-%H%M%S)

.PHONY: help
help:
	@echo "Helm Refactored Commands:"
	@echo "  make deps          - Update Helm dependencies"
	@echo "  make lint          - Lint Helm charts"
	@echo "  make template      - Generate templates for review"
	@echo "  make install       - Install to test namespace"
	@echo "  make upgrade       - Upgrade existing installation"
	@echo "  make uninstall     - Remove installation"
	@echo "  make test          - Run Helm tests"

.PHONY: deps
deps:
	@echo "Updating Helm dependencies..."
	@helm dependency update

.PHONY: lint
lint:
	@echo "Linting Helm charts..."
	@helm lint .
	@helm lint ./charts/base-microservice
	@helm lint ./charts/monitor-ui

.PHONY: template
template:
	@echo "Generating templates..."
	@helm template $(HELM_RELEASE_NAME) . \
		--namespace $(K8S_NAMESPACE) \
		-f values.yaml \
		-f values-dev.yaml \
		--debug > generated-manifests.yaml
	@echo "Templates saved to generated-manifests.yaml"

.PHONY: dry-run
dry-run:
	@echo "Performing dry-run installation..."
	@helm install $(HELM_RELEASE_NAME) . \
		--namespace $(K8S_NAMESPACE) \
		--create-namespace \
		-f values.yaml \
		-f values-dev.yaml \
		--dry-run

.PHONY: install
install: deps
	@echo "Installing to namespace $(K8S_NAMESPACE)..."
	@kubectl create namespace $(K8S_NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	@helm install $(HELM_RELEASE_NAME) . \
		--namespace $(K8S_NAMESPACE) \
		-f values.yaml \
		-f values-dev.yaml \
		--wait --timeout 5m

.PHONY: upgrade
upgrade: deps
	@echo "Upgrading installation..."
	@helm upgrade $(HELM_RELEASE_NAME) . \
		--namespace $(K8S_NAMESPACE) \
		-f values.yaml \
		-f values-dev.yaml \
		--wait --timeout 5m

.PHONY: uninstall
uninstall:
	@echo "Uninstalling..."
	@helm uninstall $(HELM_RELEASE_NAME) \
		--namespace $(K8S_NAMESPACE) || true
	@kubectl delete namespace $(K8S_NAMESPACE) --ignore-not-found=true

.PHONY: status
status:
	@echo "Checking status..."
	@helm status $(HELM_RELEASE_NAME) -n $(K8S_NAMESPACE)
	@echo ""
	@kubectl get all -n $(K8S_NAMESPACE)

.PHONY: test
test:
	@echo "Running Helm tests..."
	@helm test $(HELM_RELEASE_NAME) -n $(K8S_NAMESPACE)

.PHONY: values-diff
values-diff:
	@echo "Comparing values files..."
	@diff -u ../helm/values.yaml values.yaml || true
