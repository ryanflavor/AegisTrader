#!/bin/bash

# Run AegisSDK Examples
# This script runs various SDK examples to demonstrate functionality

set -e

EXAMPLES_DIR="packages/aegis-sdk/aegis_sdk/examples/quickstart"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "====================================="
echo "AegisSDK Examples Runner"
echo "====================================="

# Function to display menu
show_menu() {
    echo ""
    echo "Select an example to run:"
    echo ""
    echo "  ${BLUE}Basic Services:${NC}"
    echo "  1) Echo Service (Load-Balanced)"
    echo "  2) Echo Single Service (Single-Active)"
    echo "  3) Pattern Comparison Demo"
    echo ""
    echo "  ${BLUE}Advanced Services:${NC}"
    echo "  4) Order Processing Service"
    echo "  5) Event Publisher"
    echo "  6) Event Subscriber"
    echo "  7) Metrics Collector"
    echo ""
    echo "  ${BLUE}Client Applications:${NC}"
    echo "  8) Interactive CLI Client"
    echo "  9) Service Discovery Explorer"
    echo "  10) Event Stream Monitor"
    echo "  11) Failover Tester"
    echo "  12) Load Testing Client"
    echo ""
    echo "  ${BLUE}Demonstrations:${NC}"
    echo "  13) Run Load-Balanced Demo (3 instances)"
    echo "  14) Run Single-Active Demo (with failover)"
    echo "  15) Run Event-Driven Demo"
    echo "  16) Run Full System Demo"
    echo ""
    echo "  0) Exit"
    echo ""
}

# Function to run a Python script
run_script() {
    local script=$1
    local description=$2

    echo -e "\n${YELLOW}Starting: $description${NC}"
    echo "Running: python $EXAMPLES_DIR/$script"
    echo "----------------------------------------"

    python "$EXAMPLES_DIR/$script"

    echo "----------------------------------------"
    echo -e "${GREEN}✓ Completed: $description${NC}"
}

# Function to run script in background
run_background() {
    local script=$1
    local description=$2

    echo -e "${YELLOW}Starting in background: $description${NC}"
    python "$EXAMPLES_DIR/$script" &
    local pid=$!
    echo "  PID: $pid"
    return $pid
}

# Function to run load-balanced demo
run_load_balanced_demo() {
    echo -e "\n${BLUE}=== Load-Balanced Service Demo ===${NC}"
    echo "This demo shows multiple instances handling requests"
    echo ""

    # Start 3 echo service instances
    echo "Starting 3 Echo Service instances..."

    PIDS=()
    for i in 1 2 3; do
        INSTANCE_ID="echo-$i" python "$EXAMPLES_DIR/echo_service.py" &
        PIDS+=($!)
        echo -e "${GREEN}✓ Started instance echo-$i (PID: ${PIDS[-1]})${NC}"
        sleep 1
    done

    echo ""
    echo "Waiting for services to register..."
    sleep 3

    # Run client to test
    echo -e "\n${YELLOW}Running client to test load balancing...${NC}"
    python "$EXAMPLES_DIR/echo_client.py"

    # Cleanup
    echo -e "\n${YELLOW}Stopping services...${NC}"
    for pid in "${PIDS[@]}"; do
        kill $pid 2>/dev/null || true
    done

    echo -e "${GREEN}✓ Demo completed${NC}"
}

# Function to run single-active demo
run_single_active_demo() {
    echo -e "\n${BLUE}=== Single-Active Service Demo ===${NC}"
    echo "This demo shows failover between instances"
    echo ""

    # Start 2 single-active instances
    echo "Starting 2 Single-Active instances..."

    INSTANCE_ID="single-1" python "$EXAMPLES_DIR/echo_single_service.py" &
    PID1=$!
    echo -e "${GREEN}✓ Started instance single-1 (PID: $PID1)${NC}"

    sleep 2

    INSTANCE_ID="single-2" python "$EXAMPLES_DIR/echo_single_service.py" &
    PID2=$!
    echo -e "${GREEN}✓ Started instance single-2 (PID: $PID2)${NC}"

    echo ""
    echo "Waiting for leader election..."
    sleep 3

    # Test initial state
    echo -e "\n${YELLOW}Testing initial leader...${NC}"
    python -c "
import asyncio
from aegis_sdk.developer import quick_setup

async def test():
    client = await quick_setup('test-client')
    try:
        result = await client.call_rpc('echo-single', 'echo', {'message': 'Hello Leader'})
        print(f'Response from leader: {result}')
    except Exception as e:
        print(f'Error: {e}')
    finally:
        await client.stop()

asyncio.run(test())
"

    # Kill the leader
    echo -e "\n${YELLOW}Killing current leader (PID: $PID1)...${NC}"
    kill $PID1 2>/dev/null

    echo "Waiting for failover..."
    sleep 3

    # Test after failover
    echo -e "\n${YELLOW}Testing new leader after failover...${NC}"
    python -c "
import asyncio
from aegis_sdk.developer import quick_setup

async def test():
    client = await quick_setup('test-client')
    try:
        result = await client.call_rpc('echo-single', 'echo', {'message': 'Hello New Leader'})
        print(f'Response from new leader: {result}')
    except Exception as e:
        print(f'Error: {e}')
    finally:
        await client.stop()

asyncio.run(test())
"

    # Cleanup
    echo -e "\n${YELLOW}Stopping services...${NC}"
    kill $PID2 2>/dev/null || true

    echo -e "${GREEN}✓ Demo completed${NC}"
}

# Function to run event-driven demo
run_event_demo() {
    echo -e "\n${BLUE}=== Event-Driven Demo ===${NC}"
    echo "This demo shows event publishing and subscription"
    echo ""

    # Start subscriber
    echo "Starting Event Subscriber..."
    python "$EXAMPLES_DIR/event_subscriber.py" &
    SUB_PID=$!
    echo -e "${GREEN}✓ Started subscriber (PID: $SUB_PID)${NC}"

    sleep 2

    # Start publisher
    echo -e "\n${YELLOW}Starting Event Publisher...${NC}"
    python "$EXAMPLES_DIR/event_publisher.py"

    # Let subscriber process remaining events
    sleep 2

    # Cleanup
    echo -e "\n${YELLOW}Stopping subscriber...${NC}"
    kill $SUB_PID 2>/dev/null || true

    echo -e "${GREEN}✓ Demo completed${NC}"
}

# Function to run full system demo
run_full_demo() {
    echo -e "\n${BLUE}=== Full System Demo ===${NC}"
    echo "This demo runs multiple services and clients together"
    echo ""

    PIDS=()

    # Start services
    echo "Starting services..."

    # Echo services
    for i in 1 2; do
        INSTANCE_ID="echo-$i" python "$EXAMPLES_DIR/echo_service.py" &
        PIDS+=($!)
        echo -e "${GREEN}✓ Echo Service $i (PID: ${PIDS[-1]})${NC}"
    done

    # Order service
    python "$EXAMPLES_DIR/order_service.py" &
    PIDS+=($!)
    echo -e "${GREEN}✓ Order Service (PID: ${PIDS[-1]})${NC}"

    # Metrics collector
    python "$EXAMPLES_DIR/metrics_collector.py" &
    PIDS+=($!)
    echo -e "${GREEN}✓ Metrics Collector (PID: ${PIDS[-1]})${NC}"

    # Event subscriber
    python "$EXAMPLES_DIR/event_subscriber.py" &
    PIDS+=($!)
    echo -e "${GREEN}✓ Event Subscriber (PID: ${PIDS[-1]})${NC}"

    echo ""
    echo "Waiting for services to start..."
    sleep 5

    # Run various clients
    echo -e "\n${YELLOW}Running Service Explorer...${NC}"
    timeout 5 python "$EXAMPLES_DIR/service_explorer.py" || true

    echo -e "\n${YELLOW}Running Event Publisher...${NC}"
    python "$EXAMPLES_DIR/event_publisher.py"

    echo -e "\n${YELLOW}Running Load Tester...${NC}"
    python "$EXAMPLES_DIR/load_tester.py"

    # Cleanup
    echo -e "\n${YELLOW}Stopping all services...${NC}"
    for pid in "${PIDS[@]}"; do
        kill $pid 2>/dev/null || true
    done

    echo -e "${GREEN}✓ Full demo completed${NC}"
}

# Function to check prerequisites
check_prerequisites() {
    # Check if NATS is accessible
    if ! nc -zv localhost 4222 &>/dev/null; then
        echo -e "${RED}✗ NATS is not accessible on localhost:4222${NC}"
        echo "  Please run setup_k8s_dev.sh first"
        exit 1
    fi

    # Check if Python packages are available
    if ! python -c "import aegis_sdk" 2>/dev/null; then
        echo -e "${RED}✗ AegisSDK is not installed${NC}"
        echo "  Please install the SDK first:"
        echo "  cd packages/aegis-sdk && pip install -e ."
        exit 1
    fi
}

# Main loop
main() {
    check_prerequisites

    while true; do
        show_menu
        read -p "Enter choice [0-16]: " choice

        case $choice in
            1) run_script "echo_service.py" "Echo Service (Load-Balanced)" ;;
            2) run_script "echo_single_service.py" "Echo Single Service (Single-Active)" ;;
            3) run_script "pattern_comparison.py" "Pattern Comparison Demo" ;;
            4) run_script "order_service.py" "Order Processing Service" ;;
            5) run_script "event_publisher.py" "Event Publisher" ;;
            6) run_script "event_subscriber.py" "Event Subscriber" ;;
            7) run_script "metrics_collector.py" "Metrics Collector" ;;
            8) run_script "interactive_client.py" "Interactive CLI Client" ;;
            9) run_script "service_explorer.py" "Service Discovery Explorer" ;;
            10) run_script "event_monitor.py" "Event Stream Monitor" ;;
            11) run_script "failover_tester.py" "Failover Tester" ;;
            12) run_script "load_tester.py" "Load Testing Client" ;;
            13) run_load_balanced_demo ;;
            14) run_single_active_demo ;;
            15) run_event_demo ;;
            16) run_full_demo ;;
            0)
                echo "Exiting..."
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid choice. Please try again.${NC}"
                ;;
        esac

        echo ""
        read -p "Press Enter to continue..."
    done
}

# Handle cleanup on exit
trap 'echo -e "\n${YELLOW}Cleaning up...${NC}"; kill $(jobs -p) 2>/dev/null' EXIT

# Run main
main
