#!/bin/bash
# AegisTrader 一键部署脚本
# 用法: ./deploy.sh [环境] [命名空间]
# 示例: ./deploy.sh dev aegis-dev

set -e

# 加载部署配置
[ -f .deploy.env ] && source .deploy.env

# 默认值
ENVIRONMENT="${1:-dev}"
NAMESPACE="${2:-${K8S_NAMESPACE:-aegis-trader}}"
KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-aegis-local}"
HELM_RELEASE_NAME="${HELM_RELEASE_NAME:-aegis-trader}"
HELM="${HELM:-helm}"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 打印带颜色的信息
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# 检查必要的工具
check_requirements() {
    info "检查必要工具..."

    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        error "Docker 未安装"
    fi

    # 检查 kubectl
    if ! command -v kubectl &> /dev/null; then
        error "kubectl 未安装"
    fi

    # 检查 helm
    if ! command -v helm &> /dev/null; then
        error "Helm 未安装"
    fi

    # 检查 kind (如果使用本地集群)
    if [[ "$ENVIRONMENT" == "dev" ]] && ! command -v kind &> /dev/null; then
        error "Kind 未安装 (本地开发需要)"
    fi

    info "所有必要工具已就绪"
}

# 检查或创建 Kind 集群
setup_kind_cluster() {
    if [[ "$ENVIRONMENT" == "dev" ]]; then
        info "检查 Kind 集群..."
        if ! kind get clusters | grep -q "$KIND_CLUSTER_NAME"; then
            warn "Kind 集群不存在，正在创建..."
            kind create cluster --name "$KIND_CLUSTER_NAME" --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: ${KIND_UI_CONTAINER_PORT:-30100}
    hostPort: ${KIND_UI_HOST_PORT:-3100}
    protocol: TCP
  - containerPort: ${KIND_API_CONTAINER_PORT:-30800}
    hostPort: ${KIND_API_HOST_PORT:-8100}
    protocol: TCP
EOF
        else
            info "Kind 集群已存在"
        fi
    fi
}

# 构建 Docker 镜像
build_images() {
    info "构建 Docker 镜像..."

    # 使用 docker-compose 构建
    docker-compose build

    # 重新标记镜像以匹配 Helm values
    docker tag ${DOCKER_API_IMAGE:-aegistrader-monitor-api}:latest ${K8S_API_IMAGE:-aegis-trader/monitor-api}:latest
    docker tag ${DOCKER_UI_IMAGE:-aegistrader-monitor-ui}:latest ${K8S_UI_IMAGE:-aegis-trader/monitor-ui}:latest

    info "Docker 镜像构建完成"
}

# 加载镜像到 Kind 集群
load_images_to_kind() {
    if [[ "$ENVIRONMENT" == "dev" ]]; then
        info "加载镜像到 Kind 集群..."

        # 使用更可靠的方式加载镜像
        docker save ${K8S_API_IMAGE:-aegis-trader/monitor-api}:latest | docker exec -i ${KIND_CLUSTER_NAME}-control-plane ctr -n k8s.io images import -
        docker save ${K8S_UI_IMAGE:-aegis-trader/monitor-ui}:latest | docker exec -i ${KIND_CLUSTER_NAME}-control-plane ctr -n k8s.io images import -

        info "镜像加载完成"
    fi
}

# 清理旧的部署
cleanup_old_deployment() {
    info "清理旧的部署..."

    # 检查是否存在旧的 Helm release
    if helm list -n "$NAMESPACE" | grep -q aegis-trader; then
        warn "发现旧的部署，正在卸载..."
        helm uninstall aegis-trader -n "$NAMESPACE" || true

        # 等待资源清理
        sleep 5
    fi

    # 如果命名空间存在，删除它
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        warn "删除命名空间 $NAMESPACE..."
        kubectl delete namespace "$NAMESPACE" --force --grace-period=0 || true

        # 等待命名空间删除
        while kubectl get namespace "$NAMESPACE" &> /dev/null; do
            warn "等待命名空间删除..."
            sleep 2
        done
    fi

    info "清理完成"
}

# 部署到 Kubernetes
deploy_to_k8s() {
    info "部署到 Kubernetes..."

    # 进入 helm 目录
    cd helm

    # 构建 values 文件列表
    VALUES_FILES="-f values.yaml"

    # 添加 Docker Compose 镜像名称覆盖
    if [[ -f "values.docker-compose.yaml" ]]; then
        VALUES_FILES="$VALUES_FILES -f values.docker-compose.yaml"
        info "使用 Docker Compose 镜像配置"
    fi

    # 生成并添加部署配置
    info "生成部署配置..."
    ./generate-helm-values.sh
    if [[ -f "values.deployment.yaml" ]]; then
        VALUES_FILES="$VALUES_FILES -f values.deployment.yaml"
        info "使用部署配置文件"
    fi

    # 添加环境特定配置
    if [[ -f "values.${ENVIRONMENT}.yaml" ]]; then
        VALUES_FILES="$VALUES_FILES -f values.${ENVIRONMENT}.yaml"
        info "使用环境配置文件: values.${ENVIRONMENT}.yaml"
    fi

    # 执行部署
    ${HELM} upgrade --install ${HELM_RELEASE_NAME} . \
        --namespace "$NAMESPACE" \
        $VALUES_FILES \
        --timeout 10m \
        --wait \
        --debug

    cd ..

    info "部署完成"
}

# 等待部署就绪
wait_for_deployment() {
    info "等待所有 Pod 就绪..."

    # 等待所有 Pod 运行
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=aegis-trader -n "$NAMESPACE" --timeout=300s || {
        error "部署超时，请检查 Pod 状态"
    }

    info "所有 Pod 已就绪"
}

# 验证部署
verify_deployment() {
    info "验证部署..."

    # 显示部署状态
    echo
    kubectl get all -n "$NAMESPACE"
    echo

    # 如果是本地开发，设置端口转发
    if [[ "$ENVIRONMENT" == "dev" ]]; then
        info "设置端口转发..."

        # 杀死旧的端口转发进程
        pkill -f "kubectl port-forward" || true

        # 启动新的端口转发
        kubectl port-forward svc/${UI_SERVICE_NAME:-${HELM_RELEASE_NAME}-monitor-ui} ${UI_PORT:-3100}:${UI_PORT:-3100} -n "$NAMESPACE" > /dev/null 2>&1 &
        kubectl port-forward svc/${API_SERVICE_NAME:-${HELM_RELEASE_NAME}-monitor-api} ${API_PORT:-8100}:${API_PORT:-8100} -n "$NAMESPACE" > /dev/null 2>&1 &

        sleep 2

        # 测试服务
        info "测试服务健康状态..."
        if curl -s http://localhost:${API_PORT:-8100}/health | grep -q "healthy"; then
            info "API 服务正常 ✓"
        else
            warn "API 服务可能未就绪"
        fi

        echo
        info "🎉 部署成功！"
        info "访问地址："
        info "  - UI: http://localhost:${UI_PORT:-3100}"
        info "  - API: http://localhost:${API_PORT:-8100}"
        info "  - API Health: http://localhost:${API_PORT:-8100}/health"
    else
        info "部署成功！"
    fi
}

# 主函数
main() {
    echo "==================================="
    echo " AegisTrader 一键部署脚本"
    echo " 环境: $ENVIRONMENT"
    echo " 命名空间: $NAMESPACE"
    echo "==================================="
    echo

    # 执行部署流程
    check_requirements
    setup_kind_cluster
    build_images
    load_images_to_kind
    cleanup_old_deployment
    deploy_to_k8s
    wait_for_deployment
    verify_deployment

    echo
    info "部署完成！使用以下命令查看日志："
    info "  kubectl logs -f deployment/aegis-trader-monitor-api -n $NAMESPACE"
    info "  kubectl logs -f deployment/aegis-trader-monitor-ui -n $NAMESPACE"
}

# 执行主函数
main
