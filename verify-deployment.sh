#!/bin/bash
# 一键部署验证脚本

set -e

echo "🔍 AegisTrader 一键部署验证"
echo "============================="
echo ""

# 检查必需的工具
echo "1️⃣ 检查必需工具..."
MISSING_TOOLS=0

check_tool() {
    if command -v $1 &> /dev/null; then
        echo "   ✅ $1 已安装"
    else
        echo "   ❌ $1 未安装"
        MISSING_TOOLS=$((MISSING_TOOLS + 1))
    fi
}

check_tool docker
check_tool docker-compose
check_tool kubectl
check_tool helm
check_tool make

if [ $MISSING_TOOLS -gt 0 ]; then
    echo ""
    echo "❌ 缺少必需的工具，请先安装"
    exit 1
fi

echo ""
echo "2️⃣ 检查必需文件..."
MISSING_FILES=0

check_file() {
    if [ -f "$1" ]; then
        echo "   ✅ $1"
    else
        echo "   ❌ $1 缺失"
        MISSING_FILES=$((MISSING_FILES + 1))
    fi
}

check_file "docker-compose.yaml"
check_file ".deploy.env"
check_file "Makefile"
check_file "port-forward.sh"
check_file "helm/generate-helm-values.sh"
check_file "helm/values.yaml"
check_file "helm/values.docker-compose.yaml"
check_file "helm/Chart.yaml"

if [ $MISSING_FILES -gt 0 ]; then
    echo ""
    echo "❌ 缺少必需的文件"
    exit 1
fi

echo ""
echo "3️⃣ 检查 Kubernetes 集群..."
if kubectl cluster-info &> /dev/null; then
    echo "   ✅ Kubernetes 集群可访问"
    CLUSTER_TYPE=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}' | grep -q "kind" && echo "Kind" || echo "Other")
    echo "   📍 集群类型: $CLUSTER_TYPE"
else
    echo "   ❌ 无法访问 Kubernetes 集群"
    echo "   💡 请确保已启动 Kind 集群或配置了 kubeconfig"
    exit 1
fi

echo ""
echo "4️⃣ 检查 Docker 服务..."
if docker info &> /dev/null; then
    echo "   ✅ Docker 服务正在运行"
else
    echo "   ❌ Docker 服务未运行"
    exit 1
fi

echo ""
echo "5️⃣ 验证 make 命令..."
echo "   检查 make dev-deploy 依赖链..."
if make -n dev-deploy &> /dev/null; then
    echo "   ✅ make dev-deploy 命令可用"
else
    echo "   ❌ make dev-deploy 命令有问题"
    exit 1
fi

echo ""
echo "6️⃣ 检查部署状态..."
if helm list -n aegis-trader 2>/dev/null | grep -q "aegis-trader"; then
    echo "   ⚠️  已存在部署，可以使用 'make smart-deploy' 智能更新"
    HELM_STATUS=$(helm status aegis-trader -n aegis-trader 2>/dev/null | grep STATUS | awk '{print $2}')
    echo "   📊 当前状态: $HELM_STATUS"
else
    echo "   ✅ 没有现有部署，可以执行全新安装"
fi

echo ""
echo "========== 验证结果 =========="
echo "✅ 所有检查通过！"
echo ""
echo "🚀 可用的一键部署命令:"
echo "   make smart-deploy  # 智能部署（推荐）"
echo "   make dev-deploy    # 全新部署"
echo "   make dev-update    # 更新现有部署"
echo ""
echo "📋 部署后可用命令:"
echo "   make dev-forward   # 启动端口转发"
echo "   make k8s-status    # 查看部署状态"
echo "   make dev-logs      # 查看服务日志"
echo ""