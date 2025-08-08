# AegisSDK Examples Documentation

This guide provides detailed walkthroughs of all SDK examples with expected outputs and explanations.

## Table of Contents

1. [Basic Services](#basic-services)
2. [Advanced Services](#advanced-services)
3. [Client Applications](#client-applications)
4. [Pattern Demonstrations](#pattern-demonstrations)

---

## Basic Services

### Echo Service (Load-Balanced)

**File:** `examples/quickstart/echo_service.py`

**Purpose:** Demonstrates the basic load-balanced service pattern where multiple instances automatically share requests.

**Run Command:**
```bash
# Start multiple instances
INSTANCE_ID=echo-1 python echo_service.py &
INSTANCE_ID=echo-2 python echo_service.py &
INSTANCE_ID=echo-3 python echo_service.py &
```

**Expected Output:**
```
[echo-1] Starting Echo Service...
[echo-1] Service registered successfully
[echo-1] Listening for RPC calls on 'echo.echo'
[echo-2] Starting Echo Service...
[echo-2] Service registered successfully
[echo-2] Listening for RPC calls on 'echo.echo'
[echo-3] Starting Echo Service...
[echo-3] Service registered successfully
[echo-3] Listening for RPC calls on 'echo.echo'
```

**When clients call the service:**
```
[echo-1] Received echo request: {'message': 'Hello'}
[echo-2] Received echo request: {'message': 'World'}
[echo-3] Received echo request: {'message': 'Test'}
```

**Key Concepts:**
- Automatic load distribution via NATS queue groups
- Horizontal scaling by adding more instances
- No leader election - all instances are equal

---

### Echo Single Service (Single-Active)

**File:** `examples/quickstart/echo_single_service.py`

**Purpose:** Demonstrates the single-active pattern where only one leader processes exclusive requests.

**Run Command:**
```bash
# Start two instances
INSTANCE_ID=single-1 python echo_single_service.py &
INSTANCE_ID=single-2 python echo_single_service.py &
```

**Expected Output:**
```
[single-1] Starting Single-Active Echo Service...
[single-1] Participating in leader election...
[single-1] ✓ Became LEADER
[single-1] Ready to process exclusive requests

[single-2] Starting Single-Active Echo Service...
[single-2] Participating in leader election...
[single-2] Standby mode - ready for failover
```

**During failover (kill single-1):**
```
[single-2] Leader heartbeat missed
[single-2] Starting leader election...
[single-2] ✓ Became LEADER
[single-2] Failover complete in 1.8 seconds
```

**Key Concepts:**
- Leader election via NATS KV
- Automatic failover on leader failure
- Standby instances ready for immediate takeover

---

## Advanced Services

### Order Processing Service

**File:** `examples/quickstart/order_service.py`

**Purpose:** Shows a realistic stateful service using single-active pattern with domain-driven design.

**Run Command:**
```bash
python order_service.py
```

**Expected Output:**
```
[OrderService] Starting Order Processing Service...
[OrderService] Initialized with SingleActiveService pattern
[OrderService] Leader election: ACTIVE
[OrderService] Ready to process orders

Processing order: ORD-001
  Status: PENDING → VALIDATED → PROCESSING → COMPLETED

Order Statistics:
  Total Orders: 156
  Completed: 142
  Failed: 3
  Average Processing Time: 234ms
```

**Client interaction:**
```python
# Client code
response = await client.call_rpc("order-processor", "create_order", {
    "customer_id": "CUST-123",
    "items": [{"sku": "PROD-A", "quantity": 2}],
    "total": 99.99
})
```

**Expected Response:**
```json
{
  "order_id": "ORD-20240115-001",
  "status": "CREATED",
  "estimated_completion": "2024-01-15T10:30:00Z"
}
```

**Key Concepts:**
- Domain models (Order, OrderItem, OrderStatus)
- State management with exactly-once semantics
- Business logic encapsulation
- Idempotent operations

---

### Event Publisher/Subscriber

**File:** `examples/quickstart/event_publisher.py` & `event_subscriber.py`

**Purpose:** Demonstrates event-driven architecture with multiple subscription modes.

**Run Publisher:**
```bash
python event_publisher.py
```

**Publisher Output:**
```
[EventPublisher] Starting event stream...
→ Publishing: orders.created {order_id: ORD-001}
→ Publishing: payments.processed {amount: 99.99}
→ Publishing: inventory.updated {sku: PROD-A, qty: -2}
→ Publishing: orders.shipped {tracking: TRK-123}

Published 4 events in 1.2 seconds
```

**Run Subscriber:**
```bash
python event_subscriber.py
```

**Subscriber Output:**
```
[EventSubscriber] Subscribing to event streams...
[COMPETE mode] orders.* - Load balanced consumption
[BROADCAST mode] notifications.* - All instances receive
[EXCLUSIVE mode] audit.* - Single consumer only

← Received: orders.created {order_id: ORD-001}
  Processing order creation...
← Received: payments.processed {amount: 99.99}
  Updating payment records...
← Received: inventory.updated {sku: PROD-A, qty: -2}
  Adjusting inventory levels...
```

**Key Concepts:**
- COMPETE: Load-balanced event consumption
- BROADCAST: All subscribers receive events
- EXCLUSIVE: Single subscriber pattern
- Event routing via subject hierarchies

---

### Metrics Collector

**File:** `examples/quickstart/metrics_collector.py`

**Purpose:** Shows how to collect and expose service metrics through metadata.

**Run Command:**
```bash
python metrics_collector.py
```

**Expected Output:**
```
[MetricsCollector] Starting metrics collection...
[MetricsCollector] Enriching service metadata...

Current Metrics:
┌─────────────────────────────────────┐
│ Service Health Score: 98.5/100      │
│ Request Rate: 1,234 req/min         │
│ Error Rate: 0.12%                   │
│ P50 Latency: 12ms                   │
│ P99 Latency: 145ms                  │
│ Memory Usage: 234 MB                │
│ Active Connections: 42              │
└─────────────────────────────────────┘

Performance Grade: A
Status: HEALTHY
```

**Metadata exposed to monitor-api:**
```json
{
  "service": "metrics-collector",
  "instance": "collector-1",
  "metadata": {
    "metrics": {
      "health_score": 98.5,
      "request_rate": 1234,
      "error_rate": 0.0012,
      "latency_p50": 12,
      "latency_p99": 145
    },
    "performance_grade": "A",
    "last_updated": "2024-01-15T10:00:00Z"
  }
}
```

**Key Concepts:**
- Metadata enrichment pattern
- Observability without external dependencies
- Performance grading algorithms
- Real-time metrics updates

---

## Client Applications

### Interactive CLI Client

**File:** `examples/quickstart/interactive_client.py`

**Purpose:** REPL interface for testing services interactively.

**Run Command:**
```bash
python interactive_client.py
```

**Expected Interaction:**
```
AegisSDK Interactive Client
==========================
Type 'help' for commands, 'exit' to quit

aegis> discover
Discovering services...
Found 3 services:
  - echo (3 instances)
  - order-processor (1 instance)
  - metrics-collector (1 instance)

aegis> call echo echo {"message": "Hello"}
Calling echo.echo...
Response: {"echo": "Hello", "from": "echo-2", "timestamp": 1705315200}
Time: 12ms

aegis> health echo
Checking health of 'echo' service...
Instance echo-1: HEALTHY (heartbeat: 2s ago)
Instance echo-2: HEALTHY (heartbeat: 1s ago)
Instance echo-3: HEALTHY (heartbeat: 3s ago)

aegis> benchmark echo echo 100
Running benchmark: 100 requests to echo.echo
Progress: [████████████████████] 100/100
Results:
  Success: 100 (100.0%)
  Failed: 0 (0.0%)
  Avg Latency: 8.3ms
  P50: 7ms, P95: 12ms, P99: 18ms
```

**Key Features:**
- Service discovery
- Dynamic RPC invocation
- Health monitoring
- Performance benchmarking
- Command history

---

### Service Explorer

**File:** `examples/quickstart/service_explorer.py`

**Purpose:** Visual service discovery and exploration tool.

**Run Command:**
```bash
python service_explorer.py
```

**Expected Output:**
```
╔══════════════════════════════════════╗
║     AegisSDK Service Explorer        ║
╚══════════════════════════════════════╝

Service Registry Tree:
├── echo/
│   ├── echo-1 [ACTIVE] ♥ 2s
│   ├── echo-2 [ACTIVE] ♥ 1s
│   └── echo-3 [ACTIVE] ♥ 3s
├── order-processor/
│   └── order-1 [LEADER] ♥ 1s
└── metrics-collector/
    └── metrics-1 [ACTIVE] ♥ 2s

Select a service to inspect (1-3):
1. echo
2. order-processor
3. metrics-collector

> 2

Order Processor Details:
========================
Service: order-processor
Instance: order-1
Status: LEADER
Version: 1.0.0
Uptime: 00:15:23
Metadata:
  orders_processed: 156
  error_rate: 0.019
  avg_processing_time: 234ms
RPC Methods:
  - create_order
  - get_order_status
  - cancel_order
```

**Key Features:**
- Tree view of services
- Real-time status updates
- Metadata inspection
- Method discovery
- Health indicators (♥ = heartbeat)

---

### Failover Tester

**File:** `examples/quickstart/failover_tester.py`

**Purpose:** Measures and validates failover behavior.

**Run Command:**
```bash
python failover_tester.py
```

**Expected Output:**
```
AegisSDK Failover Tester
========================
Testing failover for single-active services...

Setup: Starting 3 instances of test-service
  ✓ Instance test-1 started
  ✓ Instance test-2 started
  ✓ Instance test-3 started

Initial State:
  Leader: test-1
  Standbys: test-2, test-3

Test 1: Kill leader and measure failover time
  → Sending continuous requests...
  → Killing leader (test-1)...
  ✗ Request failed at T+0.0s
  ✗ Request failed at T+0.5s
  ✗ Request failed at T+1.0s
  ✓ Request succeeded at T+1.8s (new leader: test-2)

  Failover Time: 1.8 seconds
  Downtime: 1.8 seconds
  Failed Requests: 3

Test 2: Rapid failovers
  → Killing test-2...
  Failover to test-3 in 1.6s
  → Killing test-3...
  No standbys available - service down

Summary Report:
===============
Average Failover Time: 1.7s
Min Failover: 1.6s
Max Failover: 1.8s
Availability: 98.2%
Meet SLA (<2s): ✓ YES
```

**Key Measurements:**
- Failover detection time
- Leader election duration
- Request failure count
- Recovery time objective (RTO)
- Service availability percentage

---

### Load Testing Client

**File:** `examples/quickstart/load_tester.py`

**Purpose:** Performance and scalability testing tool.

**Run Command:**
```bash
python load_tester.py
```

**Expected Output:**
```
AegisSDK Load Tester
===================
Target: echo service
Pattern: constant
Rate: 100 req/s
Duration: 60s

Starting load test...
[▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓] 100%

Results Summary:
================
Total Requests: 6,000
Successful: 5,994 (99.9%)
Failed: 6 (0.1%)

Latency Distribution:
  P50: 8ms
  P75: 11ms
  P90: 18ms
  P95: 25ms
  P99: 42ms
  P99.9: 78ms
  Max: 125ms

Throughput:
  Achieved: 99.9 req/s
  Target: 100 req/s

Error Analysis:
  Timeouts: 4
  Connection Errors: 2
  Service Errors: 0

Load Distribution:
  echo-1: 2,001 requests (33.4%)
  echo-2: 1,998 requests (33.3%)
  echo-3: 1,995 requests (33.3%)
```

**Load Patterns Available:**
- **Constant**: Steady rate
- **Ramp**: Gradual increase
- **Spike**: Sudden burst
- **Wave**: Sinusoidal pattern
- **Random**: Variable rate

---

## Pattern Demonstrations

### Pattern Comparison Demo

**File:** `examples/quickstart/pattern_comparison.py`

**Purpose:** Side-by-side comparison of service patterns.

**Run Command:**
```bash
python pattern_comparison.py
```

**Expected Output:**
```
════════════════════════════════════════
    Service Pattern Comparison Demo
════════════════════════════════════════

Starting services for comparison...
✓ Load-Balanced Service (3 instances)
✓ Single-Active Service (3 instances)
✓ External Client (monitor pattern)

─────────────────────────────────────────
Test 1: Load Distribution
─────────────────────────────────────────
Sending 30 requests to each pattern...

Load-Balanced Results:
  Instance lb-1: 10 requests (33.3%)
  Instance lb-2: 11 requests (36.7%)
  Instance lb-3: 9 requests (30.0%)
  Distribution: BALANCED ✓

Single-Active Results:
  Instance sa-1 (LEADER): 30 requests (100%)
  Instance sa-2 (STANDBY): 0 requests (0%)
  Instance sa-3 (STANDBY): 0 requests (0%)
  Distribution: SINGLE-ACTIVE ✓

External Client Results:
  Observing without processing
  Services discovered: 6
  Metrics collected: 180 data points

─────────────────────────────────────────
Test 2: Failover Behavior
─────────────────────────────────────────
Killing leader of each pattern...

Load-Balanced (kill lb-1):
  Impact: None - lb-2 and lb-3 continue
  Downtime: 0ms
  Requests rerouted: Immediately

Single-Active (kill sa-1):
  New leader elected: sa-2
  Failover time: 1.7s
  Requests queued: 3
  Requests resumed: After election

External Client:
  Detected failure: Within 1s
  Updated monitoring: Automatic
  No service impact: Observer only

─────────────────────────────────────────
Pattern Selection Guide:
─────────────────────────────────────────
Use Load-Balanced when:
  ✓ Stateless processing
  ✓ High throughput needed
  ✓ Horizontal scaling required

Use Single-Active when:
  ✓ Stateful operations
  ✓ Ordered processing required
  ✓ Resource contention concerns

Use External Client when:
  ✓ Monitoring/observing
  ✓ Management operations
  ✓ Not providing service
```

---

## Running Multiple Examples Together

### Demo Script

Create a script to run a complete demonstration:

```bash
#!/bin/bash
# demo.sh - Run complete AegisSDK demonstration

# Start services
echo "Starting services..."
python echo_service.py &
python order_service.py &
python metrics_collector.py &
python event_subscriber.py &

sleep 5

# Run clients
echo "Running client demonstrations..."
python interactive_client.py < demo_commands.txt
python service_explorer.py --auto
python load_tester.py --quick

# Cleanup
kill $(jobs -p)
```

### Expected System Behavior

When running all examples together:

1. **Service Registration**: All services appear in registry within 2-3 seconds
2. **Load Distribution**: Requests spread evenly across load-balanced instances
3. **Leader Election**: Single-active services elect leaders within 1 second
4. **Event Flow**: Events published by one service consumed by subscribers
5. **Metrics Collection**: All services report metrics to collector
6. **Failover**: Leader failures detected and recovered within 2 seconds

---

## Troubleshooting Examples

### Common Issues and Solutions

**Service doesn't start:**
```
Error: Cannot connect to NATS
Solution: Ensure port-forwarding is active
Command: kubectl port-forward -n aegis-trader svc/aegis-trader-nats 4222:4222
```

**RPC calls timeout:**
```
Error: RPC timeout after 5 seconds
Solution: Check if service is registered
Command: python service_explorer.py
```

**Leader election fails:**
```
Error: Cannot acquire leader lock
Solution: Check KV bucket exists
Command: nats kv ls
```

**Events not received:**
```
Error: No events in subscriber
Solution: Verify subject matching
Debug: Enable verbose logging with DEBUG=true
```

---

## Performance Expectations

Based on local K8s testing:

| Metric | Expected Value | Notes |
|--------|---------------|-------|
| Service Registration | < 1 second | After NATS connection |
| RPC Latency (P50) | 5-10ms | Local network |
| RPC Latency (P99) | 20-50ms | With load |
| Failover Time | 1.5-2.0s | Aggressive policy |
| Event Delivery | < 5ms | JetStream enabled |
| Load Capacity | 1000+ req/s | Per service instance |
| Memory Usage | 50-100 MB | Per Python process |

---

## Next Steps

After running these examples:

1. **Modify Examples**: Change parameters and observe behavior
2. **Combine Patterns**: Mix patterns in your services
3. **Build Your Own**: Use examples as templates
4. **Test at Scale**: Deploy to real K8s cluster
5. **Monitor Performance**: Use metrics collector pattern

For more details, see:
- [Quickstart Guide](quickstart.md)
- [Troubleshooting Guide](troubleshooting.md)
- [Architecture Documentation](../../../docs/architecture.md)
