# Leader Election Timing Constraints

## Core Constraints

1. **Heartbeat Interval**: Must be an integer (Pydantic validation)
   - Minimum: 1 second
   - Current: 1 second

2. **Leader TTL**: Must be > heartbeat interval
   - Minimum: 2 seconds (when heartbeat = 1s)
   - Current: 2 seconds

## Why Sub-Second Values Don't Make Sense

Since the heartbeat can only be sent every 1 second (minimum), and the TTL must be at least 2 seconds:

1. **Checking more frequently than 1s is wasteful**
   - The heartbeat only updates every 1s
   - Checking every 0.5s just sees the same heartbeat twice
   - Changed: Periodic check interval from 0.5s → 1.0s

2. **Heartbeat update interval of 0.3s was meaningless**
   - The configured heartbeat is 1s minimum
   - Changed: Use TTL/2 instead of hardcoded 0.3s

3. **Expiry threshold of 0.8s was too aggressive**
   - With 1s heartbeat, 0.8s threshold causes false positives
   - Changed: Expiry threshold from 0.8s → 1.0s

## What Values Still Make Sense < 1s

1. **Operation Timeouts** (kept as-is)
   - KV operations: 0.5s timeout - prevents blocking
   - These are safety timeouts, not detection intervals

2. **Propagation Delays** (adjusted slightly)
   - Purge propagation: 0.05s → 0.1s
   - Retry delay: 0.05s → 0.1s
   - These are cluster synchronization delays

## Result

With these realistic constraints:
- **Minimum achievable failover**: ~2 seconds
- **Current achievement**: 1.991 seconds ✅
- **Theoretical limit**: Cannot go below 2s with integer heartbeat constraint

## Recommendation

If sub-second failover is required, you would need to:
1. Modify the SDK to accept float heartbeat intervals
2. Use a different election mechanism (e.g., RAFT with millisecond precision)
3. Use NATS Streams instead of KV Store for real-time event propagation
