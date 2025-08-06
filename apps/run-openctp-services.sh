#!/bin/bash
# 启动 OpenCTP 行情和交易服务

set -e

echo "OpenCTP Services Launcher"
echo "========================="

# 检查 NATS 是否运行
echo "Checking NATS connection..."
if ! nc -z localhost 4222 2>/dev/null; then
    echo "ERROR: NATS is not running on localhost:4222"
    echo "Please start NATS first with: docker run -d -p 4222:4222 nats:latest"
    exit 1
fi
echo "✓ NATS is running"

# 复制环境文件
if [ ! -f "vnpy-market-demo/.env" ]; then
    cp .env.openctp vnpy-market-demo/.env
    echo "Created vnpy-market-demo/.env"
fi

if [ ! -f "vnpy-trading-demo/.env" ]; then
    cp .env.openctp vnpy-trading-demo/.env
    echo "Created vnpy-trading-demo/.env"
fi

# 启动服务的函数
start_service() {
    local service_name=$1
    local service_dir=$2
    local log_file=$3

    echo ""
    echo "Starting $service_name..."
    cd "$service_dir" || exit

    # 确保日志目录存在
    mkdir -p logs

    # 启动服务
    nohup uv run python main.py > "logs/$log_file" 2>&1 &
    local pid=$!
    echo "Started $service_name with PID: $pid"

    cd - > /dev/null
}

# 停止所有服务
stop_all() {
    echo ""
    echo "Stopping all services..."
    pkill -f "vnpy-market-demo/main.py" || true
    pkill -f "vnpy-trading-demo/main.py" || true
    echo "All services stopped"
}

# 查看日志
view_logs() {
    echo ""
    echo "=== Market Service Logs ==="
    tail -20 vnpy-market-demo/logs/market.log 2>/dev/null || echo "No market logs found"

    echo ""
    echo "=== Trading Service Logs ==="
    tail -20 vnpy-trading-demo/logs/trading.log 2>/dev/null || echo "No trading logs found"
}

# 主菜单
echo ""
echo "Select operation:"
echo "1. Start Market Data Service (行情服务)"
echo "2. Start Trading Service (交易服务)"
echo "3. Start Both Services (启动两个服务)"
echo "4. Stop All Services (停止所有服务)"
echo "5. View Service Logs (查看日志)"
echo "6. Run Test Client (运行测试客户端)"

read -p "Enter your choice (1-6): " choice

case $choice in
    1)
        start_service "Market Data Service" "vnpy-market-demo" "market.log"
        echo ""
        echo "Waiting for service to initialize..."
        sleep 5
        tail -10 vnpy-market-demo/logs/market.log
        ;;
    2)
        start_service "Trading Service" "vnpy-trading-demo" "trading.log"
        echo ""
        echo "Waiting for service to initialize..."
        sleep 5
        tail -10 vnpy-trading-demo/logs/trading.log
        ;;
    3)
        start_service "Market Data Service" "vnpy-market-demo" "market.log"
        sleep 3
        start_service "Trading Service" "vnpy-trading-demo" "trading.log"
        echo ""
        echo "Waiting for services to initialize..."
        sleep 8
        view_logs
        ;;
    4)
        stop_all
        ;;
    5)
        view_logs
        ;;
    6)
        echo "Running test client..."
        uv run python test-client.py
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "Done!"
