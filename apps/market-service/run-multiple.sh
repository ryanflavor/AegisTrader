#!/bin/bash
# 多实例启动脚本 - 用于测试选举和故障转移

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查参数
if [ "$#" -lt 1 ]; then
    echo "用法: $0 <实例数量> [start|stop|status|restart]"
    echo "示例:"
    echo "  $0 3 start   # 启动3个实例"
    echo "  $0 3 stop    # 停止所有实例"
    echo "  $0 3 status  # 查看实例状态"
    echo "  $0 3 restart # 重启所有实例"
    exit 1
fi

NUM_INSTANCES=$1
ACTION=${2:-start}

# 加载环境变量
load_env() {
    if [ -f "../../.env.test.local" ]; then
        export $(grep -v '^#' ../../.env.test.local | xargs)
    elif [ -f ".env.test.local" ]; then
        export $(grep -v '^#' .env.test.local | xargs)
    elif [ -f ".env" ]; then
        export $(grep -v '^#' .env | xargs)
    fi
    export ENABLE_CTP_GATEWAY=true
}

# 启动单个实例
start_instance() {
    local instance_num=$1
    local instance_id="ctp-gateway-instance-$instance_num"

    # 检查是否已经在运行
    if [ -f "instance_$instance_num.pid" ]; then
        local pid=$(cat instance_$instance_num.pid)
        if ps -p $pid > /dev/null 2>&1; then
            echo -e "${YELLOW}实例 $instance_num 已在运行 (PID: $pid)${NC}"
            return
        fi
    fi

    echo -e "${GREEN}启动实例 $instance_num: $instance_id${NC}"

    # 设置环境变量并启动
    load_env
    export SERVICE_INSTANCE_ID=$instance_id

    # 在后台运行并保存 PID
    nohup uv run python main.py > logs/instance_$instance_num.log 2>&1 &
    local pid=$!
    echo $pid > instance_$instance_num.pid

    echo -e "${GREEN}  ✓ 已启动，PID: $pid${NC}"
    echo -e "${GREEN}  ✓ 日志文件: logs/instance_$instance_num.log${NC}"
}

# 停止单个实例
stop_instance() {
    local instance_num=$1

    if [ -f "instance_$instance_num.pid" ]; then
        local pid=$(cat instance_$instance_num.pid)
        if ps -p $pid > /dev/null 2>&1; then
            echo -e "${RED}停止实例 $instance_num (PID: $pid)${NC}"
            kill $pid 2>/dev/null
            rm -f instance_$instance_num.pid
            echo -e "${GREEN}  ✓ 已停止${NC}"
        else
            echo -e "${YELLOW}实例 $instance_num 未在运行${NC}"
            rm -f instance_$instance_num.pid
        fi
    else
        echo -e "${YELLOW}实例 $instance_num 未找到 PID 文件${NC}"
    fi
}

# 查看实例状态
check_status() {
    local instance_num=$1

    if [ -f "instance_$instance_num.pid" ]; then
        local pid=$(cat instance_$instance_num.pid)
        if ps -p $pid > /dev/null 2>&1; then
            # 检查是否是 leader
            local is_leader=$(tail -100 logs/instance_$instance_num.log 2>/dev/null | grep -c "Won election\|became leader\|ACTIVE.*leader")
            if [ $is_leader -gt 0 ]; then
                echo -e "${GREEN}实例 $instance_num: 运行中 (PID: $pid) - LEADER${NC}"
            else
                echo -e "${BLUE}实例 $instance_num: 运行中 (PID: $pid) - STANDBY${NC}"
            fi
        else
            echo -e "${RED}实例 $instance_num: 已停止${NC}"
        fi
    else
        echo -e "${YELLOW}实例 $instance_num: 未启动${NC}"
    fi
}

# 创建日志目录
mkdir -p logs

# 执行操作
case $ACTION in
    start)
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}启动 $NUM_INSTANCES 个实例${NC}"
        echo -e "${GREEN}========================================${NC}\n"

        for i in $(seq 1 $NUM_INSTANCES); do
            start_instance $i
            sleep 2  # 实例之间间隔2秒启动
        done

        echo -e "\n${GREEN}所有实例已启动${NC}"
        echo -e "${YELLOW}提示: 使用 '$0 $NUM_INSTANCES status' 查看状态${NC}"
        echo -e "${YELLOW}提示: 使用 'tail -f logs/instance_*.log' 查看实时日志${NC}"
        ;;

    stop)
        echo -e "${RED}========================================${NC}"
        echo -e "${RED}停止所有实例${NC}"
        echo -e "${RED}========================================${NC}\n"

        for i in $(seq 1 $NUM_INSTANCES); do
            stop_instance $i
        done

        echo -e "\n${GREEN}所有实例已停止${NC}"
        ;;

    status)
        echo -e "${BLUE}========================================${NC}"
        echo -e "${BLUE}实例状态${NC}"
        echo -e "${BLUE}========================================${NC}\n"

        for i in $(seq 1 $NUM_INSTANCES); do
            check_status $i
        done

        # 显示选举信息
        echo -e "\n${BLUE}选举信息:${NC}"
        leader_count=$(grep -l "Won election\|became leader" logs/instance_*.log 2>/dev/null | wc -l)
        if [ $leader_count -gt 0 ]; then
            echo -e "${GREEN}  当前有 $leader_count 个 Leader${NC}"
        else
            echo -e "${YELLOW}  未检测到 Leader${NC}"
        fi
        ;;

    restart)
        echo -e "${YELLOW}========================================${NC}"
        echo -e "${YELLOW}重启所有实例${NC}"
        echo -e "${YELLOW}========================================${NC}\n"

        # 先停止
        for i in $(seq 1 $NUM_INSTANCES); do
            stop_instance $i
        done

        echo -e "\n${GREEN}等待 3 秒...${NC}\n"
        sleep 3

        # 再启动
        for i in $(seq 1 $NUM_INSTANCES); do
            start_instance $i
            sleep 2
        done

        echo -e "\n${GREEN}所有实例已重启${NC}"
        ;;

    *)
        echo -e "${RED}无效的操作: $ACTION${NC}"
        echo "可用操作: start, stop, status, restart"
        exit 1
        ;;
esac
