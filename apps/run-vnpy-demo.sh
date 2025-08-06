#!/bin/bash
# VNPy Demo 启动脚本

echo "VNPy Demo Launcher"
echo "=================="

# 检查NATS是否运行
echo "Checking NATS connection..."
if ! nc -z localhost 4222 2>/dev/null; then
    echo "ERROR: NATS is not running on localhost:4222"
    echo "Please start NATS first with: docker run -p 4222:4222 nats:latest"
    exit 1
fi
echo "✓ NATS is running"

# 创建.env文件
setup_env() {
    local service_dir=$1
    if [ ! -f "$service_dir/.env" ]; then
        echo "Creating .env file for $service_dir..."
        cp "$service_dir/.env.example" "$service_dir/.env"
        echo "Please edit $service_dir/.env and add your OpenCTP password"
    fi
}

# 设置环境文件
setup_env "vnpy-market-demo"
setup_env "vnpy-trading-demo"

# 启动服务的函数
start_service() {
    local service_name=$1
    local service_dir=$2

    echo ""
    echo "Starting $service_name..."
    cd "$service_dir" || exit

    # 安装依赖
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python -m venv venv
    fi

    echo "Installing dependencies..."
    source venv/bin/activate
    pip install -q -r requirements.txt

    # 启动服务
    python main.py &

    cd - > /dev/null
}

# 主菜单
echo ""
echo "Select operation:"
echo "1. Start Market Data Service"
echo "2. Start Trading Service"
echo "3. Start Both Services"
echo "4. Run Test Client"
echo "5. Stop All Services"

read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        start_service "Market Data Service" "vnpy-market-demo"
        ;;
    2)
        start_service "Trading Service" "vnpy-trading-demo"
        ;;
    3)
        start_service "Market Data Service" "vnpy-market-demo"
        sleep 2
        start_service "Trading Service" "vnpy-trading-demo"
        ;;
    4)
        echo "Running test client..."
        python test-client.py
        ;;
    5)
        echo "Stopping all services..."
        pkill -f "vnpy-market-demo"
        pkill -f "vnpy-trading-demo"
        echo "All services stopped"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "Done!"
