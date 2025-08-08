#!/bin/bash

# Test Failover Scenarios for AegisSDK
# This script tests various failover scenarios to validate HA behavior

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "====================================="
echo "AegisSDK Failover Testing"
echo "====================================="

# Configuration
NAMESPACE="aegis-trader"
TEST_SERVICE="failover-test-service"
INSTANCES=3
FAILOVER_DELAY=2

# Function to create test service script
create_test_service() {
    cat > /tmp/failover_test_service.py << 'EOF'
import asyncio
import sys
import os
from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.domain.value_objects import FailoverPolicy

instance_id = os.environ.get("INSTANCE_ID", "test-1")

async def main():
    service = SingleActiveService(
        name="failover-test",
        instance_id=instance_id,
        nats_url="nats://localhost:4222",
        failover_policy=FailoverPolicy.aggressive()
    )

    @service.rpc("status")
    async def get_status(params):
        return {
            "instance": instance_id,
            "role": "leader" if service.is_leader else "standby",
            "timestamp": asyncio.get_event_loop().time()
        }

    @service.rpc("process")
    async def process_request(params):
        if not service.is_leader:
            raise Exception("NOT_ACTIVE")
        return {
            "processed_by": instance_id,
            "data": params.get("data", ""),
            "timestamp": asyncio.get_event_loop().time()
        }

    print(f"[{instance_id}] Starting service...")
    await service.start()

    try:
        while True:
            role = "LEADER" if service.is_leader else "STANDBY"
            print(f"[{instance_id}] Status: {role}")
            await asyncio.sleep(2)
    except KeyboardInterrupt:
        print(f"[{instance_id}] Shutting down...")
    finally:
        await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
EOF
}

# Function to create test client script
create_test_client() {
    cat > /tmp/failover_test_client.py << 'EOF'
import asyncio
import time
from aegis_sdk.developer import quick_setup

async def main():
    client = await quick_setup("failover-test-client")

    print("Testing failover behavior...")
    print("-" * 40)

    failures = 0
    successes = 0
    start_time = time.time()

    for i in range(20):
        try:
            result = await client.call_rpc(
                "failover-test",
                "process",
                {"data": f"request-{i}"},
                timeout=5
            )
            print(f"✓ Request {i}: Processed by {result['processed_by']}")
            successes += 1
        except Exception as e:
            print(f"✗ Request {i}: Failed - {e}")
            failures += 1

        await asyncio.sleep(0.5)

    elapsed = time.time() - start_time

    print("-" * 40)
    print(f"Results:")
    print(f"  Total Requests: {successes + failures}")
    print(f"  Successful: {successes}")
    print(f"  Failed: {failures}")
    print(f"  Success Rate: {successes/(successes+failures)*100:.1f}%")
    print(f"  Total Time: {elapsed:.1f}s")

    await client.stop()

if __name__ == "__main__":
    asyncio.run(main())
EOF
}

# Function to run basic failover test
test_basic_failover() {
    echo -e "\n${BLUE}=== Test 1: Basic Failover ===${NC}"
    echo "Starting 3 instances and killing the leader"

    # Start instances
    PIDS=()
    for i in 1 2 3; do
        INSTANCE_ID="instance-$i" python /tmp/failover_test_service.py &
        PIDS+=($!)
        echo -e "${GREEN}✓ Started instance-$i (PID: ${PIDS[-1]})${NC}"
        sleep 1
    done

    echo "Waiting for leader election..."
    sleep 3

    # Find and kill the leader
    echo -e "${YELLOW}Killing the leader (PID: ${PIDS[0]})...${NC}"
    kill ${PIDS[0]} 2>/dev/null

    echo "Waiting for failover..."
    sleep $FAILOVER_DELAY

    # Test that new leader responds
    echo -e "${YELLOW}Testing new leader...${NC}"
    python /tmp/failover_test_client.py

    # Cleanup
    for pid in "${PIDS[@]:1}"; do
        kill $pid 2>/dev/null || true
    done

    echo -e "${GREEN}✓ Test completed${NC}"
}

# Function to test rapid failover
test_rapid_failover() {
    echo -e "\n${BLUE}=== Test 2: Rapid Failover ===${NC}"
    echo "Testing multiple failovers in quick succession"

    # Start instances
    PIDS=()
    for i in 1 2 3; do
        INSTANCE_ID="rapid-$i" python /tmp/failover_test_service.py &
        PIDS+=($!)
        echo -e "${GREEN}✓ Started rapid-$i (PID: ${PIDS[-1]})${NC}"
        sleep 1
    done

    echo "Waiting for leader election..."
    sleep 3

    # Start continuous client
    python /tmp/failover_test_client.py &
    CLIENT_PID=$!

    # Kill leaders repeatedly
    for round in 1 2; do
        echo -e "${YELLOW}Round $round: Killing a leader...${NC}"
        # Find and kill first running process
        for i in "${!PIDS[@]}"; do
            if ps -p ${PIDS[$i]} > /dev/null 2>&1; then
                echo "  Killing PID: ${PIDS[$i]}"
                kill ${PIDS[$i]} 2>/dev/null
                unset PIDS[$i]
                break
            fi
        done
        sleep $FAILOVER_DELAY
    done

    # Wait for client to finish
    wait $CLIENT_PID

    # Cleanup remaining
    for pid in "${PIDS[@]}"; do
        kill $pid 2>/dev/null || true
    done

    echo -e "${GREEN}✓ Test completed${NC}"
}

# Function to test network partition
test_network_partition() {
    echo -e "\n${BLUE}=== Test 3: Network Partition Simulation ===${NC}"
    echo "Simulating network issues by blocking NATS connection"

    # This would require iptables or similar, simplified for demo
    echo -e "${YELLOW}Note: This test requires root access for network manipulation${NC}"
    echo "Skipping actual network partition test in demo mode"

    # Alternative: Test connection loss recovery
    echo "Testing connection loss recovery..."

    INSTANCE_ID="partition-test" python /tmp/failover_test_service.py &
    PID=$!

    sleep 3

    echo -e "${YELLOW}Service is running...${NC}"
    echo "In a real test, we would:"
    echo "  1. Block port 4222 using iptables"
    echo "  2. Wait for timeout"
    echo "  3. Restore connectivity"
    echo "  4. Verify service recovers"

    sleep 2

    kill $PID 2>/dev/null || true

    echo -e "${GREEN}✓ Test completed${NC}"
}

# Function to test failover timing
test_failover_timing() {
    echo -e "\n${BLUE}=== Test 4: Failover Timing Measurement ===${NC}"
    echo "Measuring exact failover time"

    cat > /tmp/timing_test.py << 'EOF'
import asyncio
import time
from aegis_sdk.developer import quick_setup

async def main():
    client = await quick_setup("timing-test-client")

    print("Measuring failover timing...")
    print("Making continuous requests while leader is killed...")
    print("-" * 40)

    request_times = []
    failure_start = None
    failure_end = None

    for i in range(100):
        start = time.time()
        try:
            result = await client.call_rpc(
                "failover-test",
                "process",
                {"data": f"timing-{i}"},
                timeout=0.5
            )
            elapsed = time.time() - start
            request_times.append(elapsed)

            if failure_start and not failure_end:
                failure_end = time.time()
                print(f"✓ Service recovered at request {i}")

            if elapsed < 0.1:
                print(".", end="", flush=True)
            else:
                print(f"\n  Request {i}: {elapsed:.3f}s (slow)")

        except Exception as e:
            if not failure_start:
                failure_start = time.time()
                print(f"\n✗ Failure detected at request {i}")
            print("x", end="", flush=True)

        await asyncio.sleep(0.1)

    print("\n" + "-" * 40)

    if failure_start and failure_end:
        failover_time = failure_end - failure_start
        print(f"Failover Time: {failover_time:.3f} seconds")

    if request_times:
        avg_time = sum(request_times) / len(request_times)
        max_time = max(request_times)
        print(f"Average Response Time: {avg_time:.3f}s")
        print(f"Max Response Time: {max_time:.3f}s")

    await client.stop()

if __name__ == "__main__":
    asyncio.run(main())
EOF

    # Start 2 instances
    PIDS=()
    for i in 1 2; do
        INSTANCE_ID="timing-$i" python /tmp/failover_test_service.py &
        PIDS+=($!)
        echo -e "${GREEN}✓ Started timing-$i (PID: ${PIDS[-1]})${NC}"
        sleep 1
    done

    sleep 3

    # Start timing test in background
    python /tmp/timing_test.py &
    CLIENT_PID=$!

    # Wait a bit then kill leader
    sleep 3
    echo -e "${YELLOW}Killing leader now...${NC}"
    kill ${PIDS[0]} 2>/dev/null

    # Wait for test to complete
    wait $CLIENT_PID

    # Cleanup
    kill ${PIDS[1]} 2>/dev/null || true

    echo -e "${GREEN}✓ Test completed${NC}"
}

# Function to run all tests
run_all_tests() {
    create_test_service
    create_test_client

    test_basic_failover
    sleep 2

    test_rapid_failover
    sleep 2

    test_network_partition
    sleep 2

    test_failover_timing

    # Cleanup temp files
    rm -f /tmp/failover_test_service.py
    rm -f /tmp/failover_test_client.py
    rm -f /tmp/timing_test.py
}

# Function to display menu
show_menu() {
    echo ""
    echo "Select a failover test:"
    echo "  1) Basic Failover (kill leader once)"
    echo "  2) Rapid Failover (multiple kills)"
    echo "  3) Network Partition Simulation"
    echo "  4) Failover Timing Measurement"
    echo "  5) Run All Tests"
    echo "  0) Exit"
    echo ""
}

# Main function
main() {
    # Check prerequisites
    if ! nc -zv localhost 4222 &>/dev/null; then
        echo -e "${RED}✗ NATS is not accessible on localhost:4222${NC}"
        echo "  Please run setup_k8s_dev.sh first"
        exit 1
    fi

    create_test_service
    create_test_client

    while true; do
        show_menu
        read -p "Enter choice [0-5]: " choice

        case $choice in
            1) test_basic_failover ;;
            2) test_rapid_failover ;;
            3) test_network_partition ;;
            4) test_failover_timing ;;
            5) run_all_tests ;;
            0)
                echo "Cleaning up and exiting..."
                rm -f /tmp/failover_test_service.py
                rm -f /tmp/failover_test_client.py
                rm -f /tmp/timing_test.py
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

# Cleanup on exit
trap 'kill $(jobs -p) 2>/dev/null; rm -f /tmp/*.py' EXIT

# Run main
main
