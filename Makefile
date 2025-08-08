# AegisTrader Makefile - 使用优化的 Helm 结构
# 基于环境变量配置的部署管理

# 加载环境变量配置
include .deploy.env
export

# 自动生成版本标签 - 使用环境变量以保持一致性
VERSION ?= $(shell echo $$VERSION || date +$(VERSION_DATE_FORMAT))

.PHONY: help
help: ## 显示帮助信息
	@echo '╭─────────────────────────────────────────╮'
	@echo '│       AegisTrader 开发工具              │'
	@echo '╰─────────────────────────────────────────╯'
	@echo ''
	@echo '🚀 快速开始:'
	@echo '  make deploy              # 部署K8s环境 (TTL 30秒)'
	@echo '  make update              # 更新部署 (构建所有镜像)'
	@echo '  make forward-start       # 启动端口转发 (非阻塞)'
	@echo '  make forward-stop        # 停止端口转发'
	@echo '  make status              # 查看 K8s 资源状态'
	@echo ''
	@echo '⚡ 快速更新 (修改代码后):'
	@echo '  make update-api          # 只更新 Monitor API'
	@echo '  make update-ui           # 只更新 Monitor UI'
	@echo '  make update-echo         # 只更新 Echo Service (SDK示例)'
	@echo '  make update-trading      # 更新所有交易服务'
	@echo '  make update-order        # 只更新订单服务'
	@echo '  make update-pricing      # 只更新定价服务'
	@echo '  make update-risk         # 只更新风险服务'
	@echo ''
	@echo '📦 部署管理:'
	@echo '╭────────────────────┬────────────────────────────────────╮'
	@echo '│ 命令               │ 说明                               │'
	@echo '├────────────────────┼────────────────────────────────────┤'
	@awk 'BEGIN {FS = ":.*?## "} /^deploy:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^update:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^stop:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^start:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^clean:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo '╰────────────────────┴────────────────────────────────────╯'
	@echo ''
	@echo '🔗 端口转发:'
	@echo '╭────────────────────┬────────────────────────────────────╮'
	@echo '│ 命令               │ 说明                               │'
	@echo '├────────────────────┼────────────────────────────────────┤'
	@awk 'BEGIN {FS = ":.*?## "} /^forward:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^forward-start:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^forward-stop:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^forward-status:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo '╰────────────────────┴────────────────────────────────────╯'
	@echo ''
	@echo '📊 监控与调试:'
	@echo '╭────────────────────┬────────────────────────────────────╮'
	@echo '│ 命令               │ 说明                               │'
	@echo '├────────────────────┼────────────────────────────────────┤'
	@awk 'BEGIN {FS = ":.*?## "} /^status:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^logs:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^test:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^test-failover:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^test-failover-debug:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo '╰────────────────────┴────────────────────────────────────╯'
	@echo ''
	@echo '🛠️  开发工具:'
	@echo '╭────────────────────┬────────────────────────────────────╮'
	@echo '│ 命令               │ 说明                               │'
	@echo '├────────────────────┼────────────────────────────────────┤'
	@awk 'BEGIN {FS = ":.*?## "} /^shell-api:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^shell-ui:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^nats-cli:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^registry-status:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^restart-all:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^watch:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo '╰────────────────────┴────────────────────────────────────╯'
	@echo ''
	@echo '🔧 构建命令:'
	@echo '╭────────────────────┬────────────────────────────────────╮'
	@echo '│ 命令               │ 说明                               │'
	@echo '├────────────────────┼────────────────────────────────────┤'
	@awk 'BEGIN {FS = ":.*?## "} /^build-images:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^build-trading-image:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*?## "} /^load-images-to-kind:.*?## / {printf "│ \033[36m%-18s\033[0m │ %-34s │\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo '╰────────────────────┴────────────────────────────────────╯'
	@echo ''
	@echo '📌 当前配置:'
	@echo '  版本: $(VERSION)'
	@echo '  命名空间: $(K8S_NAMESPACE)'
	@echo '  集群: $(KIND_CLUSTER_NAME)'

# ==========部署命令 ==========

.PHONY: deploy
deploy: ## 部署K8s环境 (TTL 30秒自动清理)
	@echo "🚀 部署 AegisTrader (TTL 30秒自动清理)..."
	@# 获取最新的已标记镜像版本
	@API_TAG=$$(docker images $(DOCKER_API_IMAGE) --format "{{.Tag}}" | grep -E '^[0-9]{8}-[0-9]{6}$$' | head -1); \
	UI_TAG=$$(docker images $(DOCKER_UI_IMAGE) --format "{{.Tag}}" | grep -E '^[0-9]{8}-[0-9]{6}$$' | head -1); \
	ECHO_TAG=$$(docker images aegis-echo-service --format "{{.Tag}}" | grep -E '^[0-9]{8}-[0-9]{6}$$' | head -1); \
	if [ -z "$$API_TAG" ] || [ -z "$$UI_TAG" ] || [ -z "$$ECHO_TAG" ]; then \
		echo "❌ 未找到已标记的镜像，请先运行 make build-images"; \
		exit 1; \
	fi; \
	echo "📌 使用镜像版本: API=$$API_TAG, UI=$$UI_TAG, ECHO=$$ECHO_TAG"; \
	$(MAKE) -f Makefile load-images-to-kind API_TAG=$$API_TAG UI_TAG=$$UI_TAG ECHO_TAG=$$ECHO_TAG && \
	kubectl create namespace $(K8S_NAMESPACE) --dry-run=client -o yaml | kubectl apply -f - && \
	helm dependency update $(HELM_DIR) && \
	cp $(HELM_DIR)/values-test.yaml $(HELM_DIR)/values-deploy.yaml && \
	sed -i "/monitor-api:/,/tag:/ s/tag: \".*\"/tag: \"$$API_TAG\"/" $(HELM_DIR)/values-deploy.yaml && \
	sed -i "/monitor-ui:/,/tag:/ s/tag: \".*\"/tag: \"$$UI_TAG\"/" $(HELM_DIR)/values-deploy.yaml && \
	sed -i "/echo-service:/,/tag:/ s/tag: \".*\"/tag: \"$$ECHO_TAG\"/" $(HELM_DIR)/values-deploy.yaml && \
	(timeout 120 helm install $(HELM_RELEASE_NAME) $(HELM_DIR) \
		--namespace $(K8S_NAMESPACE) \
		-f $(HELM_DIR)/values-deploy.yaml \
		--wait || echo "⚠️ Helm install timeout, continuing...") && \
	rm -f $(HELM_DIR)/values-deploy.yaml
	@echo "⏳ 配置KV bucket TTL..."
	@sleep 5
	@# 确保KV bucket有正确的TTL配置
	@kubectl exec -n $(K8S_NAMESPACE) deployment/$(NATS_SERVICE_NAME)-box -- sh -c '\
		if nats kv ls | grep -q service_registry; then \
			MAX_AGE=$$(nats kv info service_registry | grep "Maximum Age" | awk "{print \$$3}"); \
			if [ "$$MAX_AGE" = "unlimited" ] || [ "$$MAX_AGE" = "0.00s" ]; then \
				echo "♻️  重建KV bucket with TTL..."; \
				nats stream rm KV_service_registry -f 2>/dev/null; \
				nats kv add service_registry --ttl 30s --replicas 1; \
			else \
				echo "✅ KV bucket TTL已配置: $$MAX_AGE"; \
			fi \
		else \
			echo "🆕 创建KV bucket with TTL..."; \
			nats kv add service_registry --ttl 30s --replicas 1; \
		fi' 2>/dev/null || true
	@echo "✅ 部署完成 (TTL: 30秒)"
	@echo "📊 验证TTL配置："
	@kubectl exec -n $(K8S_NAMESPACE) deployment/$(NATS_SERVICE_NAME)-box -- \
		nats kv info service_registry | grep -E "Maximum Age|Bucket Name" || echo "等待NATS就绪..."
	@echo ""
	@echo "📊 使用 'make status' 查看状态"
	@echo "🔗 使用 'make forward-start' 访问服务"

.PHONY: update
update: ## 更新部署（构建所有服务）
	@# 设置版本并导出给子任务
	@export VERSION=$$(date +%Y%m%d-%H%M%S) && \
	echo "🔄 更新 AegisTrader..." && \
	echo "📌 使用镜像版本: $$VERSION" && \
	$(MAKE) -f Makefile build-images VERSION=$$VERSION && \
	$(MAKE) -f Makefile load-images VERSION=$$VERSION && \
	sed -i "s/tag: \".*\"/tag: \"$$VERSION\"/g" $(HELM_DIR)/values-test.yaml && \
	helm upgrade $(HELM_RELEASE_NAME) $(HELM_DIR) \
		--namespace $(K8S_NAMESPACE) \
		-f $(HELM_DIR)/values-test.yaml \
		--wait --timeout 3m
	@echo "✅ 更新完成!"

.PHONY: update-api
update-api: ## 快速更新 Monitor API
	@VERSION=$$(date +%Y%m%d-%H%M%S) && \
	echo "🔄 更新 Monitor API (版本: $$VERSION)..." && \
	docker-compose build monitor-api && \
	docker tag $(DOCKER_API_IMAGE):latest $(DOCKER_API_IMAGE):$$VERSION && \
	docker save $(DOCKER_API_IMAGE):$$VERSION | docker exec -i $(KIND_CONTROL_PLANE) ctr -n k8s.io images import - && \
	kubectl set image deployment/$(API_SERVICE_NAME) monitor-api=$(DOCKER_API_IMAGE):$$VERSION -n $(K8S_NAMESPACE) && \
	kubectl rollout status deployment/$(API_SERVICE_NAME) -n $(K8S_NAMESPACE) --timeout=2m
	@echo "✅ Monitor API 更新完成!"

.PHONY: update-ui
update-ui: ## 快速更新 Monitor UI
	@VERSION=$$(date +%Y%m%d-%H%M%S) && \
	echo "🔄 更新 Monitor UI (版本: $$VERSION)..." && \
	docker-compose build monitor-ui && \
	docker tag $(DOCKER_UI_IMAGE):latest $(DOCKER_UI_IMAGE):$$VERSION && \
	docker save $(DOCKER_UI_IMAGE):$$VERSION | docker exec -i $(KIND_CONTROL_PLANE) ctr -n k8s.io images import - && \
	kubectl set image deployment/$(UI_SERVICE_NAME) monitor-ui=$(DOCKER_UI_IMAGE):$$VERSION -n $(K8S_NAMESPACE) && \
	kubectl rollout status deployment/$(UI_SERVICE_NAME) -n $(K8S_NAMESPACE) --timeout=2m
	@echo "✅ Monitor UI 更新完成!"

.PHONY: update-trading
update-trading: ## 快速更新所有交易服务
	@VERSION=$$(date +%Y%m%d-%H%M%S) && \
	echo "🔨 构建交易服务镜像 (版本: $$VERSION)..." && \
	docker-compose build trading-service && \
	docker tag $(DOCKER_TRADING_IMAGE):latest $(DOCKER_TRADING_IMAGE):$$VERSION && \
	docker save $(DOCKER_TRADING_IMAGE):$$VERSION | docker exec -i $(KIND_CONTROL_PLANE) ctr -n k8s.io images import - && \
	echo "📦 更新所有交易服务..." && \
	kubectl set image deployment/$(HELM_RELEASE_NAME)-order-service order-service=$(DOCKER_TRADING_IMAGE):$$VERSION -n $(K8S_NAMESPACE) && \
	kubectl set image deployment/$(HELM_RELEASE_NAME)-pricing-service pricing-service=$(DOCKER_TRADING_IMAGE):$$VERSION -n $(K8S_NAMESPACE) && \
	kubectl set image deployment/$(HELM_RELEASE_NAME)-risk-service risk-service=$(DOCKER_TRADING_IMAGE):$$VERSION -n $(K8S_NAMESPACE) && \
	kubectl rollout status deployment/$(HELM_RELEASE_NAME)-order-service -n $(K8S_NAMESPACE) --timeout=2m && \
	kubectl rollout status deployment/$(HELM_RELEASE_NAME)-pricing-service -n $(K8S_NAMESPACE) --timeout=2m && \
	kubectl rollout status deployment/$(HELM_RELEASE_NAME)-risk-service -n $(K8S_NAMESPACE) --timeout=2m
	@echo "✅ 交易服务更新完成!"

.PHONY: update-order
update-order: ## 快速更新订单服务
	@$(MAKE) -f Makefile update-single-trading SERVICE=order

.PHONY: update-pricing
update-pricing: ## 快速更新定价服务
	@$(MAKE) -f Makefile update-single-trading SERVICE=pricing

.PHONY: update-risk
update-risk: ## 快速更新风险服务
	@$(MAKE) -f Makefile update-single-trading SERVICE=risk

.PHONY: update-echo
update-echo: ## 快速更新 Echo Service
	@VERSION=$$(date +%Y%m%d-%H%M%S) && \
	echo "🔄 更新 Echo Service (版本: $$VERSION)..." && \
	docker build --build-arg HTTP_PROXY=$(HTTP_PROXY) --build-arg HTTPS_PROXY=$(HTTPS_PROXY) --build-arg NO_PROXY=$(NO_PROXY) \
		-t aegis-echo-service:$$VERSION -f apps/echo-service/Dockerfile . && \
	docker save aegis-echo-service:$$VERSION | docker exec -i $(KIND_CONTROL_PLANE) ctr -n k8s.io images import - && \
	kubectl set image deployment/$(HELM_RELEASE_NAME)-echo-service echo-service=aegis-echo-service:$$VERSION -n $(K8S_NAMESPACE) && \
	kubectl rollout status deployment/$(HELM_RELEASE_NAME)-echo-service -n $(K8S_NAMESPACE) --timeout=2m && \
	echo "✅ Echo Service 更新完成!"

.PHONY: update-single-trading
update-single-trading: ## 更新单个交易服务（内部使用）
	@VERSION=$$(date +%Y%m%d-%H%M%S) && \
	echo "🔄 更新 $(SERVICE) 服务 (版本: $$VERSION)..." && \
	docker-compose build trading-service && \
	docker tag $(DOCKER_TRADING_IMAGE):latest $(DOCKER_TRADING_IMAGE):$$VERSION && \
	docker save $(DOCKER_TRADING_IMAGE):$$VERSION | docker exec -i $(KIND_CONTROL_PLANE) ctr -n k8s.io images import - && \
	kubectl set image deployment/$(HELM_RELEASE_NAME)-$(SERVICE)-service $(SERVICE)-service=$(DOCKER_TRADING_IMAGE):$$VERSION -n $(K8S_NAMESPACE) && \
	kubectl rollout status deployment/$(HELM_RELEASE_NAME)-$(SERVICE)-service -n $(K8S_NAMESPACE) --timeout=2m
	@echo "✅ $(SERVICE) 服务更新完成!"

.PHONY: build-images
build-images: ## 构建并标记版本化镜像
	@VERSION=$$(date +%Y%m%d-%H%M%S); \
	echo "🔨 构建 Docker 镜像 (版本: $$VERSION)..."; \
	docker-compose build monitor-api monitor-ui && \
	docker build --build-arg HTTP_PROXY=$(HTTP_PROXY) --build-arg HTTPS_PROXY=$(HTTPS_PROXY) --build-arg NO_PROXY=$(NO_PROXY) \
		-t aegis-echo-service:$$VERSION -f apps/echo-service/Dockerfile . && \
	docker tag $(DOCKER_API_IMAGE):latest $(DOCKER_API_IMAGE):$$VERSION && \
	docker tag $(DOCKER_UI_IMAGE):latest $(DOCKER_UI_IMAGE):$$VERSION && \
	docker tag aegis-echo-service:$$VERSION aegis-echo-service:latest && \
	echo "✅ 镜像构建完成: $$VERSION"

.PHONY: build-trading-image
build-trading-image: ## 构建交易服务镜像
	@echo "🔨 构建交易服务镜像..."
	@if [ -f apps/trading-service/Dockerfile ]; then \
		docker build -f apps/trading-service/Dockerfile -t $(DOCKER_TRADING_IMAGE):$(VERSION) apps/trading-service/; \
		docker tag $(DOCKER_TRADING_IMAGE):$(VERSION) $(DOCKER_TRADING_IMAGE):latest; \
	else \
		echo "⚠️  未找到 trading-service Dockerfile，跳过构建"; \
	fi

.PHONY: load-images
load-images-to-kind: ## 加载指定版本镜像到 Kind
	@echo "📦 加载镜像到 Kind..."
	@echo "📤 导出并导入 API 镜像: $(DOCKER_API_IMAGE):$(API_TAG)..."
	@docker save $(DOCKER_API_IMAGE):$(API_TAG) | docker exec -i $(KIND_CONTROL_PLANE) ctr -n k8s.io images import -
	@echo "📤 导出并导入 UI 镜像: $(DOCKER_UI_IMAGE):$(UI_TAG)..."
	@docker save $(DOCKER_UI_IMAGE):$(UI_TAG) | docker exec -i $(KIND_CONTROL_PLANE) ctr -n k8s.io images import -
	@echo "📤 导出并导入 Echo Service 镜像: aegis-echo-service:$(ECHO_TAG)..."
	@docker save aegis-echo-service:$(ECHO_TAG) | docker exec -i $(KIND_CONTROL_PLANE) ctr -n k8s.io images import -
	@echo "✅ 镜像加载完成"

.PHONY: status
status: ## 查看状态
	@echo "📊 AegisTrader状态:"
	@echo ""
	@kubectl get all -n $(K8S_NAMESPACE)
	@echo ""
	@echo "📈服务端点:"
	@kubectl get endpoints -n $(K8S_NAMESPACE)

.PHONY: forward
forward: ## 端口转发服务
	@echo "🔗 启动端口转发..."
	@echo ""
	@echo "访问地址:"
	@echo "  Monitor UI:  http://localhost:$(UI_PORT)"
	@echo "  Monitor API: http://localhost:$(API_PORT)/docs"
	@echo "  NATS:        localhost:$(NATS_FORWARD_PORT)"
	@echo ""
	@echo "按 Ctrl+C 停止端口转发"
	@echo ""
	@kubectl port-forward -n $(K8S_NAMESPACE) svc/$(UI_SERVICE_NAME) $(UI_PORT):$(UI_PORT) & \
	kubectl port-forward -n $(K8S_NAMESPACE) svc/$(API_SERVICE_NAME) $(API_PORT):$(API_PORT) & \
	kubectl port-forward -n $(K8S_NAMESPACE) svc/$(NATS_SERVICE_NAME) $(NATS_FORWARD_PORT):$(NATS_PORT) & \
	wait

.PHONY: forward-start
forward-start: ## 非阻塞启动端口转发
	@echo "🔌 启动后台端口转发..."
	@# 使用 PID 文件方式管理进程
	@if [ -f /tmp/ui-port-forward.pid ] && kill -0 $$(cat /tmp/ui-port-forward.pid) 2>/dev/null; then \
		kill $$(cat /tmp/ui-port-forward.pid) 2>/dev/null || true; \
	fi
	@if [ -f /tmp/api-port-forward.pid ] && kill -0 $$(cat /tmp/api-port-forward.pid) 2>/dev/null; then \
		kill $$(cat /tmp/api-port-forward.pid) 2>/dev/null || true; \
	fi
	@if [ -f /tmp/nats-port-forward.pid ] && kill -0 $$(cat /tmp/nats-port-forward.pid) 2>/dev/null; then \
		kill $$(cat /tmp/nats-port-forward.pid) 2>/dev/null || true; \
	fi
	@sleep 1
	@# 启动新的端口转发
	@kubectl port-forward svc/$(UI_SERVICE_NAME) $(UI_PORT):$(UI_PORT) -n $(K8S_NAMESPACE) > /tmp/ui-port-forward.log 2>&1 & echo $$! > /tmp/ui-port-forward.pid
	@kubectl port-forward svc/$(API_SERVICE_NAME) $(API_PORT):$(API_PORT) -n $(K8S_NAMESPACE) > /tmp/api-port-forward.log 2>&1 & echo $$! > /tmp/api-port-forward.pid
	@kubectl port-forward svc/$(NATS_SERVICE_NAME) $(NATS_FORWARD_PORT):$(NATS_PORT) -n $(K8S_NAMESPACE) > /tmp/nats-port-forward.log 2>&1 & echo $$! > /tmp/nats-port-forward.pid
	@sleep 2
	@# 检查状态
	@if [ -f /tmp/ui-port-forward.pid ] && kill -0 $$(cat /tmp/ui-port-forward.pid) 2>/dev/null; then \
		echo "✅ 端口转发已在后台启动"; \
		echo ""; \
		echo "📍 访问地址:"; \
		echo "   UI: http://localhost:$(UI_PORT)"; \
		echo "   API: http://localhost:$(API_PORT)/docs"; \
		echo "   NATS: nats://localhost:$(NATS_FORWARD_PORT)"; \
		echo ""; \
		echo "使用 'make forward-stop' 停止端口转发"; \
	else \
		echo "❌ 端口转发启动失败，查看日志:"; \
		echo "   tail -f /tmp/*-port-forward.log"; \
		exit 1; \
	fi

.PHONY: forward-stop
forward-stop: ## 停止端口转发
	@echo "🛑 停止端口转发..."
	@# 使用 PID 文件停止进程
	@if [ -f /tmp/ui-port-forward.pid ]; then \
		kill $$(cat /tmp/ui-port-forward.pid) 2>/dev/null || true; \
		rm -f /tmp/ui-port-forward.pid; \
	fi
	@if [ -f /tmp/api-port-forward.pid ]; then \
		kill $$(cat /tmp/api-port-forward.pid) 2>/dev/null || true; \
		rm -f /tmp/api-port-forward.pid; \
	fi
	@if [ -f /tmp/nats-port-forward.pid ]; then \
		kill $$(cat /tmp/nats-port-forward.pid) 2>/dev/null || true; \
		rm -f /tmp/nats-port-forward.pid; \
	fi
	@sleep 1
	@echo "✅ 所有端口转发已停止"

.PHONY: forward-status
forward-status: ## 查看端口转发状态
	@echo "📊 端口转发状态:"
	@ACTIVE=0; \
	if [ -f /tmp/ui-port-forward.pid ] && kill -0 $$(cat /tmp/ui-port-forward.pid) 2>/dev/null; then \
		echo "   ✅ UI 端口转发: 活动 (PID: $$(cat /tmp/ui-port-forward.pid))"; \
		ACTIVE=1; \
	else \
		echo "   ❌ UI 端口转发: 未运行"; \
	fi; \
	if [ -f /tmp/api-port-forward.pid ] && kill -0 $$(cat /tmp/api-port-forward.pid) 2>/dev/null; then \
		echo "   ✅ API 端口转发: 活动 (PID: $$(cat /tmp/api-port-forward.pid))"; \
		ACTIVE=1; \
	else \
		echo "   ❌ API 端口转发: 未运行"; \
	fi; \
	if [ -f /tmp/nats-port-forward.pid ] && kill -0 $$(cat /tmp/nats-port-forward.pid) 2>/dev/null; then \
		echo "   ✅ NATS 端口转发: 活动 (PID: $$(cat /tmp/nats-port-forward.pid))"; \
		ACTIVE=1; \
	else \
		echo "   ❌ NATS 端口转发: 未运行"; \
	fi; \
	if [ $$ACTIVE -eq 1 ]; then \
		echo ""; \
		echo "📍 访问地址:"; \
		echo "   UI: http://localhost:$(UI_PORT)"; \
		echo "   API: http://localhost:$(API_PORT)/docs"; \
		echo "   NATS: nats://localhost:$(NATS_FORWARD_PORT)"; \
	fi

.PHONY: logs
logs: ## 查看日志
	@echo "📋 查看服务日志..."
	@kubectl logs -f -n $(K8S_NAMESPACE) -l app.kubernetes.io/instance=$(HELM_RELEASE_NAME) --all-containers=true --prefix=true

.PHONY: stop
stop: ## 停止服务 (保留数据)
	@echo "⏹️  停止 AegisTrader 服务..."
	@kubectl scale deployment -n $(K8S_NAMESPACE) -l app.kubernetes.io/instance=$(HELM_RELEASE_NAME) --replicas=0
	@echo "✅ 服务已停止 (数据保留，TTL配置保持)"

.PHONY: start
start: ## 启动服务 (TTL自动生效)
	@echo "▶️  启动 AegisTrader 服务..."
	@# 恢复部署副本数
	@kubectl scale deployment -n $(K8S_NAMESPACE) aegis-trader-monitor-api --replicas=1
	@kubectl scale deployment -n $(K8S_NAMESPACE) aegis-trader-monitor-ui --replicas=1
	@kubectl scale deployment -n $(K8S_NAMESPACE) aegis-trader-echo-service --replicas=3
	@kubectl scale deployment -n $(K8S_NAMESPACE) aegis-trader-nats-box --replicas=1
	@echo "⏳ 等待服务就绪..."
	@kubectl wait --for=condition=available --timeout=120s deployment -l app.kubernetes.io/instance=$(HELM_RELEASE_NAME) -n $(K8S_NAMESPACE)
	@echo "✅ 服务已启动"
	@echo "📊 验证TTL配置:"
	@kubectl exec -n $(K8S_NAMESPACE) deployment/$(NATS_SERVICE_NAME)-box -- \
		nats stream info KV_service_registry --json 2>/dev/null | \
		jq '{name: .config.name, max_age: .config.max_age, ttl_seconds: (.config.max_age / 1000000000)}' || echo "NATS正在初始化..."

.PHONY: clean
clean: ## 清理环境
	@echo "🧹 清理环境..."
	@helm uninstall $(HELM_RELEASE_NAME) -n $(K8S_NAMESPACE) || true
	@kubectl delete namespace $(K8S_NAMESPACE) --ignore-not-found=true
	@echo "✅环境已清理"

# ========== 开发工具 ==========

.PHONY: shell-api
shell-api: ## 进入 API容器
	@kubectl exec -it deployment/$(API_SERVICE_NAME) -n $(K8S_NAMESPACE) -- /bin/bash

.PHONY: shell-ui
shell-ui: ## 进入 UI容器
	@kubectl exec -it deployment/$(UI_SERVICE_NAME) -n $(K8S_NAMESPACE) -- /bin/sh

.PHONY: nats-cli
nats-cli: ## 使用 NATS CLI
	@kubectl exec -it deployment/$(NATS_SERVICE_NAME)-box -n $(K8S_NAMESPACE) -- nats

# ========== 测试命令 ==========

.PHONY: test
test: ## 测试服务
	@echo "🧪 测试服务..."
	@echo ""
	@echo "1. 测试 NATS 连接:"
	@kubectl exec -n $(K8S_NAMESPACE) deployment/$(NATS_SERVICE_NAME)-box -- \
		nats server check connection --server=$(NATS_URL) || echo "❌ NATS 连接失败"
	@echo ""
	@echo "2. 测试 Monitor API:"
	@kubectl exec -n $(K8S_NAMESPACE) deployment/$(API_SERVICE_NAME) -- \
		curl -s http://localhost:$(API_PORT)/health | jq . || echo "❌ API 健康检查失败"
	@echo ""
	@echo "✅ 测试完成"

.PHONY: registry-status
registry-status: ## 查看服务注册表状态
	@echo "📊 服务注册表状态:"
	@echo ""
	@echo "注册的服务实例:"
	@kubectl exec -n $(K8S_NAMESPACE) deployment/$(NATS_SERVICE_NAME)-box -- \
		nats kv ls $(NATS_KV_BUCKET) 2>/dev/null | grep service-instances | \
		sed 's/service-instances_/  ✓ /' | sed 's/_/\//g' || echo "  (无服务实例)"
	@echo ""
	@echo "服务定义:"
	@kubectl exec -n $(K8S_NAMESPACE) deployment/$(NATS_SERVICE_NAME)-box -- \
		nats kv ls $(NATS_KV_BUCKET) 2>/dev/null | grep -v service-instances | \
		sed 's/^/  ✓ /' || echo "  (无服务定义)"

.PHONY: restart-all
restart-all: ## 重启所有服务
	@echo "🔄 重启所有服务..."
	@kubectl rollout restart deployment -n $(K8S_NAMESPACE) -l app.kubernetes.io/instance=$(HELM_RELEASE_NAME)
	@echo "⏳ 等待服务就绪..."
	@kubectl rollout status deployment -n $(K8S_NAMESPACE) -l app.kubernetes.io/instance=$(HELM_RELEASE_NAME) --timeout=3m
	@echo "✅ 所有服务已重启"

.PHONY: watch
watch: ## 监视服务状态变化
	@echo "👀 监视服务状态 (按 Ctrl+C 退出)..."
	@watch -n 2 'kubectl get pods -n $(K8S_NAMESPACE) | grep -E "(NAME|order|pricing|risk|monitor)" | grep -v Terminating'
