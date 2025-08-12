# Makefile for market-service
# Common development and deployment tasks

.PHONY: help
help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Environment setup
.PHONY: install
install: ## Install dependencies with uv
	uv pip install -e .

.PHONY: install-dev
install-dev: ## Install with development dependencies
	uv pip install -e ".[dev]"

.PHONY: clean
clean: ## Clean build artifacts and cache
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/ .coverage htmlcov/

# Development
.PHONY: run
run: ## Run the service locally
	uv run python main.py

.PHONY: test-local
test-local: ## Test main.py locally (quick validation before Docker build)
	@echo "🧪 Testing main.py locally for errors..."
	@if timeout 3 uv run python main.py 2>&1 | grep -E "(AttributeError|ImportError|TypeError|ModuleNotFoundError|NameError|SyntaxError)" | grep -v "Error during shutdown"; then \
		echo "❌ Local test failed! Fix errors before building Docker image."; \
		exit 1; \
	else \
		echo "✅ Local test passed (no critical errors detected)"; \
	fi

.PHONY: dev
dev: ## Run with hot reload (requires watchdog)
	uv run python -m watchdog.auto_restart --directory . --pattern "*.py" --recursive -- python main.py

# Testing
.PHONY: test
test: ## Run all tests
	uv run pytest

.PHONY: test-unit
test-unit: ## Run unit tests only
	uv run pytest tests/unit/

.PHONY: test-integration
test-integration: ## Run integration tests only
	uv run pytest tests/integration/

.PHONY: test-coverage
test-coverage: ## Run tests with coverage report
	uv run pytest --cov=market-service --cov-report=html --cov-report=term

.PHONY: test-watch
test-watch: ## Run tests in watch mode
	uv run ptw -- --testmon

# Code quality
.PHONY: format
format: ## Format code with black and ruff
	uv run black .
	uv run ruff check --fix .

.PHONY: lint
lint: ## Run linting checks
	uv run ruff check .
	uv run mypy .

.PHONY: check
check: lint test ## Run all quality checks

# Docker
.PHONY: docker-build
docker-build: test-local ## Build Docker image with versioned tag (validates code first)
	@VERSION=$$(date +%Y%m%d-%H%M%S); \
	echo "🔨 Building Docker image market-service:$$VERSION..."; \
	# Find .env file with AEGIS_ROOT by searching up the directory tree \
	ENV_FILE=$$(pwd); \
	FOUND_ROOT=false; \
	while [ "$$ENV_FILE" != "/" ]; do \
		if [ -f "$$ENV_FILE/.env" ]; then \
			if grep -q "^AEGIS_ROOT=" "$$ENV_FILE/.env" 2>/dev/null; then \
				FOUND_ROOT=true; \
				break; \
			fi; \
		fi; \
		ENV_FILE=$$(dirname "$$ENV_FILE"); \
	done; \
	if [ "$$FOUND_ROOT" = true ]; then \
		echo "Loading settings from $$ENV_FILE/.env"; \
		. "$$ENV_FILE/.env"; \
		echo "  AEGIS_ROOT: $$AEGIS_ROOT"; \
		echo "  HTTP_PROXY: $$HTTP_PROXY"; \
		echo "  HTTPS_PROXY: $$HTTPS_PROXY"; \
		echo "  NO_PROXY: $$NO_PROXY"; \
		PROJECT_DIR=$$(pwd); \
		PROJECT_PATH=$$(echo "$$PROJECT_DIR" | sed "s|$$AEGIS_ROOT/||"); \
		echo "  PROJECT_PATH: $$PROJECT_PATH"; \
		docker build --no-cache \
			--build-arg HTTP_PROXY="$$HTTP_PROXY" \
			--build-arg HTTPS_PROXY="$$HTTPS_PROXY" \
			--build-arg NO_PROXY="$$NO_PROXY" \
			--build-arg PROJECT_PATH="$$PROJECT_PATH" \
			-t market-service:$$VERSION \
			-f Dockerfile "$$AEGIS_ROOT" && \
		docker tag market-service:$$VERSION market-service:latest && \
		echo "✅ Image built: market-service:$$VERSION (also tagged as latest)"; \
	else \
		echo "Error: No .env file found with AEGIS_ROOT definition"; \
		exit 1; \
	fi

.PHONY: docker-run
docker-run: ## Run Docker container
	docker run --rm -p 8080:8080 --env-file .env market-service:latest

.PHONY: docker-compose-up
docker-compose-up: ## Start services with docker-compose
	docker-compose up -d

.PHONY: docker-compose-down
docker-compose-down: ## Stop services with docker-compose
	docker-compose down

.PHONY: docker-compose-logs
docker-compose-logs: ## Show docker-compose logs
	docker-compose logs -f

# Kind
.PHONY: kind-load
kind-load: ## Load Docker image to kind cluster
	@VERSION=$$(docker images market-service --format "{{.Tag}}" | grep -E '^[0-9]{8}-[0-9]{6}$$' | head -1); \
	if [ -z "$$VERSION" ]; then \
		echo "❌ No versioned image found, please run 'make docker-build' first"; \
		exit 1; \
	fi; \
	echo "📦 Loading image market-service:$$VERSION to kind cluster..."; \
	docker save market-service:$$VERSION | docker exec -i aegis-local-control-plane ctr -n k8s.io images import - && \
	echo "✅ Image loaded to kind: market-service:$$VERSION"

# Helm (K8s templates are Helm charts, use helm commands for deployment)
.PHONY: helm-install
helm-install: ## Install with Helm
	@VERSION=$$(docker images market-service --format "{{.Tag}}" | grep -E '^[0-9]{8}-[0-9]{6}$$' | head -1); \
	if [ -z "$$VERSION" ]; then \
		echo "❌ No versioned image found, please run 'make docker-build' first"; \
		exit 1; \
	fi; \
	helm upgrade --install market-service ./k8s \
		--set image.tag=$$VERSION \
		--set image.repository=market-service \
		-n aegis-trader

.PHONY: helm-upgrade
helm-upgrade: ## Upgrade Helm deployment
	@VERSION=$$(docker images market-service --format "{{.Tag}}" | grep -E '^[0-9]{8}-[0-9]{6}$$' | head -1); \
	if [ -z "$$VERSION" ]; then \
		echo "❌ No versioned image found, please run 'make docker-build' first"; \
		exit 1; \
	fi; \
	helm upgrade market-service ./k8s \
		--set image.tag=$$VERSION \
		--set image.repository=market-service \
		-n aegis-trader

.PHONY: helm-uninstall
helm-uninstall: ## Uninstall Helm deployment
	helm uninstall market-service -n aegis-trader

# Combined deployment
.PHONY: deploy-to-kind
deploy-to-kind: docker-build kind-load helm-install ## Build, load to kind, and deploy
	@echo "✅ Deployment complete! Check: kubectl get pods -n aegis-trader"

# Validation
.PHONY: validate
validate: ## Validate environment with aegis-validate
	aegis validate -s market-service

.PHONY: validate-k8s
validate-k8s: ## Validate Kubernetes environment
	aegis validate --environment kubernetes

# Release
.PHONY: version
version: ## Show current version
	@grep version pyproject.toml | head -1 | cut -d'"' -f2

.PHONY: release
release: check ## Create a new release (runs checks first)
	@echo "Ready for release. Update version in pyproject.toml and create git tag."
