#!/bin/bash
# 端口转发管理脚本

# 加载环境变量
[ -f .deploy.env ] && source .deploy.env

# 默认值
UI_PORT=${UI_PORT:-3100}
API_PORT=${API_PORT:-8100}
K8S_NAMESPACE=${K8S_NAMESPACE:-aegis-trader}
UI_SERVICE_NAME=${UI_SERVICE_NAME:-aegis-trader-monitor-ui}
API_SERVICE_NAME=${API_SERVICE_NAME:-aegis-trader-monitor-api}

case "$1" in
    start)
        echo "🔌 启动端口转发..."
        # 先停止已有的
        pkill -f "kubectl port-forward" 2>/dev/null || true
        sleep 1
        
        # 启动新的端口转发
        kubectl port-forward svc/${UI_SERVICE_NAME} ${UI_PORT}:${UI_PORT} -n ${K8S_NAMESPACE} > /tmp/ui-port-forward.log 2>&1 &
        kubectl port-forward svc/${API_SERVICE_NAME} ${API_PORT}:${API_PORT} -n ${K8S_NAMESPACE} > /tmp/api-port-forward.log 2>&1 &
        
        sleep 2
        
        # 检查状态
        if pgrep -f "kubectl port-forward" > /dev/null 2>&1; then
            echo "✅ 端口转发已启动"
            echo ""
            echo "📍 访问地址:"
            echo "   UI: http://localhost:${UI_PORT}"
            echo "   API: http://localhost:${API_PORT}"
        else
            echo "❌ 端口转发启动失败"
            exit 1
        fi
        ;;
        
    stop)
        echo "🛑 停止端口转发..."
        pkill -f "kubectl port-forward" 2>/dev/null || true
        sleep 1
        
        if pgrep -f "kubectl port-forward" > /dev/null 2>&1; then
            echo "⚠️  仍有端口转发进程在运行"
        else
            echo "✅ 所有端口转发已停止"
        fi
        ;;
        
    status)
        echo "📊 端口转发状态:"
        if pgrep -f "kubectl port-forward" > /dev/null 2>&1; then
            ps aux | grep "kubectl port-forward" | grep -v grep
        else
            echo "   无活动的端口转发进程"
        fi
        ;;
        
    *)
        echo "用法: $0 {start|stop|status}"
        exit 1
        ;;
esac