# AegisTrader 主 Makefile
# 提供统一的开发和部署接口

# 加载部署配置
-include .deploy.env

# 设置默认值
DOCKER_API_IMAGE ?= aegistrader-monitor-api
DOCKER_UI_IMAGE ?= aegistrader-monitor-ui
K8S_API_IMAGE ?= aegis-trader/monitor-api
K8S_UI_IMAGE ?= aegis-trader/monitor-ui
KIND_CONTROL_PLANE ?= aegis-local-control-plane
K8S_NAMESPACE ?= aegis-trader
HELM_RELEASE_NAME ?= aegis-trader

# 自动生成版本标签
VERSION ?= $(shell date +%Y%m%d-%H%M%S)

.PHONY: help
help: ## 显示帮助信息
	@echo 'AegisTrader 开发工具'
	@echo '===================='
	@echo ''
	@echo '快速开始:'
	@echo '  make smart-deploy   # 🤖 智能部署 (自动检测安装/更新) - 推荐!'
	@echo '  make dev-forward    # 🔗 启动端口转发访问服务'
	@echo '  make dev-logs       # 📋 查看所有服务日志'
	@echo '  make diagnose-images # 🔍 诊断镜像问题'
	@echo ''
	@echo '版本: $(VERSION)'
	@echo ''
	@echo '开发命令:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ========== 快速部署命令 ==========

# 智能部署 - 自动检测是安装还是更新
.PHONY: smart-deploy
smart-deploy: ensure-namespace ## 智能部署 (自动检测安装/更新)
	@echo "🤖 智能部署模式..."
	@echo "🔍 检查现有部署状态..."
	@if helm status $(HELM_RELEASE_NAME) -n $(K8S_NAMESPACE) > /dev/null 2>&1; then \
		echo "📍 检测到现有部署，执行更新..."; \
		$(MAKE) dev-update; \
	else \
		echo "📍 未检测到有效部署，清理并执行全新安装..."; \
		helm delete $(HELM_RELEASE_NAME) -n $(K8S_NAMESPACE) --no-hooks 2>/dev/null || true; \
		sleep 2; \
		$(MAKE) dev-deploy; \
	fi

.PHONY: dev-deploy
dev-deploy: ensure-namespace generate-deployment-values ## 一键部署到本地 Kubernetes (包含构建)
	@echo "🚀 开始一键部署..."
	@echo "📌 部署版本: $(VERSION)"
	@echo "🔨 构建镜像..."
	@docker-compose build
	@echo "🏷️  标记镜像版本..."
	@docker tag $(DOCKER_API_IMAGE):latest $(DOCKER_API_IMAGE):$(VERSION)
	@docker tag $(DOCKER_UI_IMAGE):latest $(DOCKER_UI_IMAGE):$(VERSION)
	@echo "📦 加载镜像到 Kind..."
	@# 导入镜像到k8s.io命名空间（Kubernetes使用的命名空间）
	@docker save $(DOCKER_API_IMAGE):$(VERSION) | docker exec -i $(KIND_CONTROL_PLANE) ctr -n k8s.io images import -
	@docker save $(DOCKER_UI_IMAGE):$(VERSION) | docker exec -i $(KIND_CONTROL_PLANE) ctr -n k8s.io images import -
	@echo "📄 生成版本配置..."
	@$(MAKE) generate-version-values VERSION=$(VERSION) VERSION=$(VERSION)
	@echo "🚀 部署到 Kubernetes..."
	@cd helm && helm install $(HELM_RELEASE_NAME) . \
		--namespace $(K8S_NAMESPACE) \
		-f values.yaml \
		-f values.version.yaml \
		-f values.docker-compose.yaml \
		-f values.deployment.yaml \
		--wait --timeout 5m
	@echo "✅ 部署完成! 版本: $(VERSION)"
	@echo "📊 使用 'make k8s-status' 查看状态"
	@echo "🔗 使用 'make dev-forward' 访问服务"

# 检查Helm release是否存在
.PHONY: check-release
check-release:
	@if ! helm list -n $(K8S_NAMESPACE) | grep -q "^$(HELM_RELEASE_NAME)\s"; then \
		echo "⚠️  Release $(HELM_RELEASE_NAME) 不存在，需要先执行初始部署"; \
		echo "💡 请执行: make dev-deploy"; \
		exit 1; \
	fi

# 生成部署配置文件
.PHONY: generate-deployment-values
generate-deployment-values:
	@echo "生成部署配置..."
	@cd helm && ./generate-helm-values.sh

# 生成版本配置文件
.PHONY: generate-version-values
generate-version-values:
	@echo "# 自动生成的版本配置" > helm/values.version.yaml
	@echo "# 生成时间: $(shell date '+%Y-%m-%d %H:%M:%S')" >> helm/values.version.yaml
	@echo "# 版本: $(VERSION)" >> helm/values.version.yaml
	@echo "" >> helm/values.version.yaml
	@echo "monitor-api:" >> helm/values.version.yaml
	@echo "  image:" >> helm/values.version.yaml
	@echo "    tag: \"$(VERSION)\"" >> helm/values.version.yaml
	@echo "    pullPolicy: IfNotPresent" >> helm/values.version.yaml
	@echo "" >> helm/values.version.yaml
	@echo "monitor-ui:" >> helm/values.version.yaml
	@echo "  image:" >> helm/values.version.yaml
	@echo "    tag: \"$(VERSION)\"" >> helm/values.version.yaml
	@echo "    pullPolicy: IfNotPresent" >> helm/values.version.yaml

.PHONY: dev-update
dev-update: check-release generate-deployment-values ## 快速更新部署 (代码修改后使用)
	@echo "🔄 快速更新部署，版本: $(VERSION)"
	@echo "🔨 构建 Docker 镜像..."
	@docker-compose build
	@echo "🏷️  标记镜像版本..."
	@docker tag $(DOCKER_API_IMAGE):latest $(DOCKER_API_IMAGE):$(VERSION)
	@docker tag $(DOCKER_UI_IMAGE):latest $(DOCKER_UI_IMAGE):$(VERSION)
	@echo "📦 加载镜像到 Kind..."
	@# 导入镜像到k8s.io命名空间（Kubernetes使用的命名空间）
	@docker save $(DOCKER_API_IMAGE):$(VERSION) | docker exec -i $(KIND_CONTROL_PLANE) ctr -n k8s.io images import -
	@docker save $(DOCKER_UI_IMAGE):$(VERSION) | docker exec -i $(KIND_CONTROL_PLANE) ctr -n k8s.io images import -
	@echo "📄 生成版本配置..."
	@$(MAKE) generate-version-values VERSION=$(VERSION)
	@echo "🚀 更新 Helm 部署..."
	@cd helm && helm upgrade $(HELM_RELEASE_NAME) . \
		--namespace $(K8S_NAMESPACE) \
		-f values.yaml \
		-f values.version.yaml \
		-f values.docker-compose.yaml \
		-f values.deployment.yaml \
		--wait --timeout 3m
	@echo "✅ 更新完成! 版本: $(VERSION)"
	@echo "🔍 查看部署状态: make k8s-status"

.PHONY: prod-deploy
prod-deploy: ## 部署到生产环境
	@./deploy.sh prod aegis-prod

# ========== Docker 命令 ==========

.PHONY: build
build: ## 构建所有 Docker 镜像
	@docker-compose build

.PHONY: build-api
build-api: ## 只构建 API 镜像
	@docker-compose build monitor-api

.PHONY: build-ui
build-ui: ## 只构建 UI 镜像
	@docker-compose build monitor-ui

.PHONY: docker-run
docker-run: ## 使用 Docker Compose 运行
	@docker-compose up -d

.PHONY: docker-stop
docker-stop: ## 停止 Docker Compose
	@docker-compose down

# ========== Kubernetes 命令 ==========

# 检查并创建命名空间
.PHONY: ensure-namespace
ensure-namespace:
	@kubectl get namespace $(K8S_NAMESPACE) > /dev/null 2>&1 || \
		(echo "📁 创建命名空间 $(K8S_NAMESPACE)..." && kubectl create namespace $(K8S_NAMESPACE))

# 诊断镜像问题
.PHONY: diagnose-images
diagnose-images: ## 诊断镜像问题
	@echo "🔍 检查本地 Docker 镜像..."
	@docker images | grep -E "$(DOCKER_API_IMAGE)|$(DOCKER_UI_IMAGE)" || echo "❌ 未找到本地镜像"
	@echo ""
	@echo "🔍 检查 Kind 集群中的镜像..."
	@docker exec $(KIND_CONTROL_PLANE) crictl images | grep -E "monitor-api|monitor-ui" || echo "❌ Kind 中未找到镜像"
	@echo ""
	@echo "🔍 检查 Pod 使用的镜像..."
	@kubectl get pods -n $(K8S_NAMESPACE) -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].image}{"\n"}{end}' || echo "❌ 无法获取 Pod 信息"

# 修复镜像拉取问题
.PHONY: fix-image-pull
fix-image-pull: ## 修复镜像拉取问题
	@echo "🔧 修复镜像拉取问题..."
	@kubectl patch deployment $(HELM_RELEASE_NAME)-monitor-api -n $(K8S_NAMESPACE) \
		-p '{"spec":{"template":{"spec":{"containers":[{"name":"monitor-api","imagePullPolicy":"IfNotPresent"}]}}}}' || true
	@kubectl patch deployment $(HELM_RELEASE_NAME)-monitor-ui -n $(K8S_NAMESPACE) \
		-p '{"spec":{"template":{"spec":{"containers":[{"name":"monitor-ui","imagePullPolicy":"IfNotPresent"}]}}}}' || true
	@echo "✅ 已设置 imagePullPolicy 为 IfNotPresent"

.PHONY: k8s-status
k8s-status: ## 查看 K8s 部署状态
	@kubectl get all -n $(K8S_NAMESPACE)

.PHONY: k8s-pods
k8s-pods: ## 查看 Pod 详细状态
	@kubectl get pods -n $(K8S_NAMESPACE) -o wide

.PHONY: dev-logs
dev-logs: ## 查看所有服务日志
	@echo "📋 查看服务日志 (Ctrl+C 退出)..."
	@kubectl logs -f -n $(K8S_NAMESPACE) -l app.kubernetes.io/instance=$(HELM_RELEASE_NAME) --all-containers=true --prefix=true

.PHONY: api-logs
api-logs: ## 查看 API 服务日志
	@kubectl logs -f deployment/$(API_SERVICE_NAME) -n $(K8S_NAMESPACE)

.PHONY: ui-logs
ui-logs: ## 查看 UI 服务日志
	@kubectl logs -f deployment/$(UI_SERVICE_NAME) -n $(K8S_NAMESPACE)

.PHONY: nats-logs
nats-logs: ## 查看 NATS 日志
	@kubectl logs -f statefulset/$(NATS_SERVICE_NAME) -n $(K8S_NAMESPACE)

# ========== 端口转发 ==========

.PHONY: port-forward
port-forward: ## 设置端口转发
	@./port-forward.sh start

.PHONY: dev-forward
dev-forward: port-forward ## 启动端口转发访问服务 (别名)

.PHONY: stop-forward
stop-forward: ## 停止端口转发
	@./port-forward.sh stop

.PHONY: forward-status
forward-status: ## 查看端口转发状态
	@./port-forward.sh status

# ========== 测试命令 ==========

.PHONY: test-api
test-api: ## 测试 API 健康检查
	@curl -s http://localhost:$(API_PORT)/health | jq || echo "API 可能未就绪"

.PHONY: test-services
test-services: ## 测试所有服务
	@echo "🧪 测试服务..."
	@make test-api
	@echo ""
	@echo "打开浏览器访问 http://localhost:$(UI_PORT) 测试 UI"

# ========== 清理命令 ==========

.PHONY: clean
clean: ## 清理所有部署
	@echo "🧹 清理部署..."
	@helm uninstall $(HELM_RELEASE_NAME) -n $(K8S_NAMESPACE) || true
	@kubectl delete namespace $(K8S_NAMESPACE) --force --grace-period=0 || true

.PHONY: clean-images
clean-images: ## 清理 Docker 镜像
	@docker rmi $(K8S_API_IMAGE):latest $(K8S_UI_IMAGE):latest || true
	@docker rmi $(DOCKER_API_IMAGE):latest $(DOCKER_UI_IMAGE):latest || true

# ========== 故障排查 ==========

.PHONY: debug-pod
debug-pod: ## 进入调试 Pod
	@kubectl run -it --rm debug --image=busybox --restart=Never -n $(K8S_NAMESPACE) -- sh

.PHONY: describe-pods
describe-pods: ## 查看所有 Pod 详情
	@kubectl describe pods -n $(K8S_NAMESPACE)

.PHONY: events
events: ## 查看集群事件
	@kubectl get events -n $(K8S_NAMESPACE) --sort-by='.lastTimestamp'

# ========== 开发工具 ==========

.PHONY: dev-shell-api
dev-shell-api: ## 进入 API 容器 Shell
	@kubectl exec -it deployment/$(API_SERVICE_NAME) -n $(K8S_NAMESPACE) -- /bin/bash

.PHONY: dev-shell-ui
dev-shell-ui: ## 进入 UI 容器 Shell
	@kubectl exec -it deployment/$(UI_SERVICE_NAME) -n $(K8S_NAMESPACE) -- /bin/sh

.PHONY: nats-cli
nats-cli: ## 使用 NATS CLI
	@kubectl exec -it deployment/$(HELM_RELEASE_NAME)-nats-box -n $(K8S_NAMESPACE) -- nats

# ========== 监控命令 ==========

.PHONY: watch-pods
watch-pods: ## 实时监控 Pod 状态
	@watch -n 2 kubectl get pods -n $(K8S_NAMESPACE)

.PHONY: top
top: ## 查看资源使用情况
	@kubectl top pods -n $(K8S_NAMESPACE)

# ========== 一键命令 ==========

.PHONY: dev
dev: dev-deploy port-forward test-services ## 完整的开发环境设置

.PHONY: restart
restart: ## 重启所有服务
	@kubectl rollout restart deployment -n $(K8S_NAMESPACE)
	@echo "⏳ 等待服务重启..."
	@kubectl rollout status deployment -n $(K8S_NAMESPACE)
	@echo "✅ 重启完成!"

.PHONY: update-api
update-api: check-release ## 只更新 API (快速迭代)
	@echo "🔄 构建 API 版本: $(VERSION)"
	@docker-compose build monitor-api
	@docker tag $(DOCKER_API_IMAGE):latest $(DOCKER_API_IMAGE):$(VERSION)
	@echo "📦 加载 API 镜像到 Kind..."
	@docker save $(DOCKER_API_IMAGE):$(VERSION) | docker exec -i $(KIND_CONTROL_PLANE) ctr -n k8s.io images import -
	@echo "🚀 更新 API 部署..."
	@kubectl set image deployment/$(HELM_RELEASE_NAME)-monitor-api monitor-api=$(DOCKER_API_IMAGE):$(VERSION) -n $(K8S_NAMESPACE) || \
		(echo "❌ 更新失败，请检查部署状态" && exit 1)
	@kubectl rollout status deployment/$(HELM_RELEASE_NAME)-monitor-api -n $(K8S_NAMESPACE) --timeout=2m

.PHONY: update-ui
update-ui: check-release ## 只更新 UI (快速迭代)
	@echo "🔄 构建 UI 版本: $(VERSION)"
	@docker-compose build monitor-ui
	@docker tag $(DOCKER_UI_IMAGE):latest $(DOCKER_UI_IMAGE):$(VERSION)
	@echo "📦 加载 UI 镜像到 Kind..."
	@docker save $(DOCKER_UI_IMAGE):$(VERSION) | docker exec -i $(KIND_CONTROL_PLANE) ctr -n k8s.io images import -
	@echo "🚀 更新 UI 部署..."
	@kubectl set image deployment/$(HELM_RELEASE_NAME)-monitor-ui monitor-ui=$(DOCKER_UI_IMAGE):$(VERSION) -n $(K8S_NAMESPACE) || \
		(echo "❌ 更新失败，请检查部署状态" && exit 1)
	@kubectl rollout status deployment/$(HELM_RELEASE_NAME)-monitor-ui -n $(K8S_NAMESPACE) --timeout=2m