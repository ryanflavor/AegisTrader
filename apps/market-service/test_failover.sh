#!/bin/bash

echo "================================================"
echo "Final Failover Test with Refactored Code"
echo "================================================"
echo ""

# Get the actual leader PID from the status
LEADER_PID=3108669

# Get precise start time
START_TIME=$(date +%s.%N)
START_TIME_DISPLAY=$(date +%H:%M:%S.%3N)

echo "Start time: $START_TIME_DISPLAY"
echo "Killing leader (PID: $LEADER_PID)..."
kill $LEADER_PID

# Monitor for failover
echo "Monitoring failover..."
TIMEOUT=5
while true; do
    # Check if instance 1 acquired leadership
    if tail -10 /home/ryan/workspace/github/AegisTrader/apps/market-service/logs/instance_1.log 2>/dev/null | grep -q "Won election\|became leader\|Successfully took over"; then
        END_TIME=$(date +%s.%N)
        FAILOVER_TIME=$(echo "$END_TIME - $START_TIME" | bc)
        LEADER="Instance 1"
        break
    fi

    # Check if instance 2 acquired leadership
    if tail -10 /home/ryan/workspace/github/AegisTrader/apps/market-service/logs/instance_2.log 2>/dev/null | grep -q "Won election\|became leader\|Successfully took over"; then
        END_TIME=$(date +%s.%N)
        FAILOVER_TIME=$(echo "$END_TIME - $START_TIME" | bc)
        LEADER="Instance 2"
        break
    fi

    # Check timeout
    CURRENT_TIME=$(date +%s.%N)
    ELAPSED=$(echo "$CURRENT_TIME - $START_TIME" | bc)
    if (( $(echo "$ELAPSED > $TIMEOUT" | bc -l) )); then
        echo "❌ Timeout: No failover detected within $TIMEOUT seconds"
        exit 1
    fi

    sleep 0.05
done

echo ""
echo "================================================"
echo "$LEADER became leader at $(date +%H:%M:%S.%3N)"
echo "Total failover time: ${FAILOVER_TIME} seconds"
echo "================================================"

if (( $(echo "$FAILOVER_TIME < 3.0" | bc -l) )); then
    echo "✅ SUCCESS: Sub-3-second failover achieved!"
else
    echo "⚠️  Failover took ${FAILOVER_TIME} seconds (target: <3s)"
fi
