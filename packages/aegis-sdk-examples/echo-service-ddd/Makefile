# Makefile for echo-service-ddd
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
	@echo "🧪 Testing main.py locally..."
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
	uv run pytest --cov=echo-service-ddd --cov-report=html --cov-report=term

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

# Docker - 自动加载根目录的 .env 文件
.PHONY: docker-build
docker-build: test-local ## Build Docker image with versioned tag (loads proxy from root .env)
	@VERSION=$$(date +%Y%m%d-%H%M%S); \
	echo "🔨 Building Docker image echo-service-ddd:$$VERSION with proxy settings..."; \
	cd ../../.. && \
	if [ -f .env ]; then \
		echo "Loading environment variables from .env"; \
		export $$(grep -v '^#' .env | xargs) && \
		echo "  HTTP_PROXY: $${HTTP_PROXY}"; \
		echo "  HTTPS_PROXY: $${HTTPS_PROXY}"; \
		echo "  NO_PROXY: $${NO_PROXY}"; \
		docker build \
			--build-arg HTTP_PROXY=$${HTTP_PROXY} \
			--build-arg HTTPS_PROXY=$${HTTPS_PROXY} \
			--build-arg NO_PROXY=$${NO_PROXY} \
			-t echo-service-ddd:$$VERSION \
			-f packages/aegis-sdk-examples/echo-service-ddd/Dockerfile.multistage .; \
		docker tag echo-service-ddd:$$VERSION echo-service-ddd:latest; \
		echo "✅ Image built: echo-service-ddd:$$VERSION (also tagged as latest)"; \
	else \
		echo "Warning: .env not found, building without proxy settings"; \
		docker build -t echo-service-ddd:$$VERSION \
			-f packages/aegis-sdk-examples/echo-service-ddd/Dockerfile.multistage .; \
		docker tag echo-service-ddd:$$VERSION echo-service-ddd:latest; \
		echo "✅ Image built: echo-service-ddd:$$VERSION (also tagged as latest)"; \
	fi

.PHONY: docker-run
docker-run: ## Run Docker container
	docker run --rm -p 8080:8080 --env-file .env echo-service-ddd:latest

.PHONY: docker-compose-up
docker-compose-up: ## Start services with docker-compose
	docker-compose up -d

.PHONY: docker-compose-down
docker-compose-down: ## Stop services with docker-compose
	docker-compose down

.PHONY: docker-compose-logs
docker-compose-logs: ## Show docker-compose logs
	docker-compose logs -f

# Kind - Load image to kind cluster (使用根目录的模式)
.PHONY: kind-load
kind-load: ## Load Docker image to kind cluster (需要先 docker-build)
	@VERSION=$$(docker images echo-service-ddd --format "{{.Tag}}" | grep -E '^[0-9]{8}-[0-9]{6}$$' | head -1); \
	if [ -z "$$VERSION" ]; then \
		echo "❌ 未找到版本化的镜像，请先运行 make docker-build"; \
		exit 1; \
	fi; \
	echo "📦 加载镜像 echo-service-ddd:$$VERSION 到 kind 集群..."; \
	docker save echo-service-ddd:$$VERSION | docker exec -i aegis-local-control-plane ctr -n k8s.io images import - && \
	echo "✅ 镜像已加载到 kind 集群: echo-service-ddd:$$VERSION"

# Helm (Note: Use Helm commands for Kubernetes deployment instead of kubectl apply)
.PHONY: helm-install
helm-install: ## Install with Helm
	helm install echo-service-ddd ./k8s -f k8s/values.yaml -n aegis-trader

.PHONY: helm-upgrade
helm-upgrade: ## Upgrade Helm deployment with latest versioned image
	@VERSION=$$(docker images echo-service-ddd --format "{{.Tag}}" | grep -E '^[0-9]{8}-[0-9]{6}$$' | head -1); \
	if [ -z "$$VERSION" ]; then \
		echo "❌ No versioned image found, please run 'make docker-build' first"; \
		exit 1; \
	fi; \
	echo "📦 Upgrading with image version: $$VERSION"; \
	helm upgrade echo-service-ddd ./k8s \
		--set image.tag=$$VERSION \
		--set image.repository=echo-service-ddd \
		-n aegis-trader

.PHONY: helm-uninstall
helm-uninstall: ## Uninstall Helm deployment
	helm uninstall echo-service-ddd -n aegis-trader

.PHONY: helm-dry-run
helm-dry-run: ## Helm install dry run to test templates
	helm install echo-service-ddd ./k8s -f k8s/values.yaml -n echo-service-ddd-test --dry-run --debug

# Combined deployment to kind (参考根目录模式)
.PHONY: deploy-to-kind
deploy-to-kind: ## Build, load to kind, and deploy with Helm
	@echo "🚀 开始部署 echo-service-ddd 到 kind 集群..."
	@$(MAKE) docker-build
	@$(MAKE) kind-load
	@VERSION=$$(docker images echo-service-ddd --format "{{.Tag}}" | grep -E '^[0-9]{8}-[0-9]{6}$$' | head -1); \
	echo "📦 使用镜像版本: $$VERSION"; \
	helm upgrade --install echo-service-ddd ./k8s \
		--set image.tag=$$VERSION \
		--set image.repository=echo-service-ddd \
		-n aegis-trader && \
	echo "⏳ 等待部署完成..." && \
	kubectl rollout status deployment/echo-service-ddd -n aegis-trader --timeout=2m && \
	echo "✅ 部署完成! 查看状态: kubectl get pods -n aegis-trader"

# Validation
.PHONY: validate
validate: ## Validate environment with aegis-validate
	aegis validate -s echo-service-ddd

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
