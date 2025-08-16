#!/usr/bin/env python3
"""
Capture REAL failover logs with timestamps
"""

import subprocess
import time
from datetime import datetime


def get_pods():
    """Get current market-service pods"""
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", "aegis-trader", "-o", "name"],
        capture_output=True,
        text=True,
    )
    return [
        line.replace("pod/", "")
        for line in result.stdout.strip().split("\n")
        if "market-service" in line
    ]


def get_leader():
    """Find current leader from logs"""
    pods = get_pods()
    for pod in pods:
        result = subprocess.run(
            ["kubectl", "logs", pod, "-n", "aegis-trader", "--tail=500"],
            capture_output=True,
            text=True,
        )
        # Check for various leader patterns
        if any(
            pattern in result.stdout
            for pattern in [
                "I am the leader",
                "Won election",
                "Leadership acquired",
                "Became leader",
            ]
        ):
            return pod
    return pods[0] if pods else None


def capture_logs_before_delete(pod):
    """Capture current state logs"""
    print(f"\n{'='*60}")
    print(f"PRE-FAILOVER LOGS - {datetime.now().isoformat()}")
    print(f"{'='*60}")

    # Get last 20 lines from the leader
    result = subprocess.run(
        ["kubectl", "logs", pod, "-n", "aegis-trader", "--tail=20"], capture_output=True, text=True
    )
    print(f"\nLeader Pod ({pod}) last logs:")
    print(result.stdout)

    # Check NATS KV store state
    print(f"\n{'='*60}")
    print("NATS KV Election State:")
    result = subprocess.run(
        [
            "kubectl",
            "exec",
            "-n",
            "aegis-trader",
            "aegis-trader-nats-box-77bf99754d-8mgsc",
            "--",
            "nats",
            "kv",
            "get",
            "election_ctp_gateway_service",
            "sticky-active__ctp-gateway-service__default",
        ],
        capture_output=True,
        text=True,
    )
    print(result.stdout if result.returncode == 0 else "No leader key found")


def delete_pod_and_monitor(leader_pod):
    """Delete pod and monitor failover with detailed logs"""
    print(f"\n{'='*60}")
    print(f"DELETING LEADER POD: {leader_pod}")
    print(f"Deletion Time: {datetime.now().isoformat()}")
    print(f"{'='*60}")

    # Delete the pod
    delete_start = time.time()
    subprocess.run(
        [
            "kubectl",
            "delete",
            "pod",
            leader_pod,
            "-n",
            "aegis-trader",
            "--force",
            "--grace-period=0",
        ],
        capture_output=True,
    )

    print(f"Pod deletion command executed at: {datetime.now().isoformat()}")

    # Monitor for new leader
    print(f"\n{'='*60}")
    print("MONITORING FOR NEW LEADER ELECTION")
    print(f"{'='*60}")

    max_attempts = 30
    for attempt in range(max_attempts):
        time.sleep(0.5)  # Check every 500ms for faster detection

        pods = get_pods()
        active_pods = [p for p in pods if p != leader_pod]

        for pod in active_pods:
            # Get recent logs
            result = subprocess.run(
                ["kubectl", "logs", pod, "-n", "aegis-trader", "--tail=50", "--since=10s"],
                capture_output=True,
                text=True,
            )

            # Check for leadership patterns
            if any(
                pattern in result.stdout
                for pattern in [
                    "Won election",
                    "Leadership acquired",
                    "Became leader",
                    "I am the leader",
                ]
            ):
                failover_time = time.time() - delete_start
                print(f"\n{'='*60}")
                print(f"NEW LEADER ELECTED: {pod}")
                print(f"Election Time: {datetime.now().isoformat()}")
                print(f"Failover Duration: {failover_time:.3f} seconds")
                print(f"{'='*60}")

                # Show the election logs
                print("\nNew Leader Election Logs:")
                for line in result.stdout.split("\n"):
                    if any(p in line for p in ["election", "leader", "Leadership"]):
                        print(line)

                return pod, failover_time

        if attempt % 2 == 0:  # Print status every second
            print(f"  Checking for new leader... ({attempt/2:.1f}s elapsed)")

    return None, time.time() - delete_start


def check_final_state():
    """Check final cluster state after failover"""
    print(f"\n{'='*60}")
    print(f"POST-FAILOVER STATE - {datetime.now().isoformat()}")
    print(f"{'='*60}")

    # List all pods
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", "aegis-trader", "-l", "app=market-service"],
        capture_output=True,
        text=True,
    )
    print("\nActive Pods:")
    print(result.stdout)

    # Check NATS KV election state
    print("\nNATS KV Election State:")
    result = subprocess.run(
        [
            "kubectl",
            "exec",
            "-n",
            "aegis-trader",
            "aegis-trader-nats-box-77bf99754d-8mgsc",
            "--",
            "nats",
            "kv",
            "get",
            "election_ctp_gateway_service",
            "sticky-active__ctp-gateway-service__default",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print(result.stdout)
    else:
        print("Could not retrieve election state")


def main():
    print(f"\n{'='*80}")
    print("REAL-TIME FAILOVER LOG CAPTURE")
    print(f"Start Time: {datetime.now().isoformat()}")
    print(f"{'='*80}")

    # Step 1: Check current deployment
    pods = get_pods()
    print(f"\nFound {len(pods)} market-service pods:")
    for pod in pods:
        print(f"  - {pod}")

    if len(pods) < 2:
        print("\nERROR: Need at least 2 pods for failover test")
        return

    # Step 2: Identify current leader
    print("\nIdentifying current leader...")
    leader = get_leader()
    if not leader:
        print("WARNING: Could not identify leader from logs, using first pod")
        leader = pods[0]
    print(f"Current Leader: {leader}")

    # Step 3: Capture pre-failover state
    capture_logs_before_delete(leader)

    # Step 4: Delete leader and monitor failover
    new_leader, failover_time = delete_pod_and_monitor(leader)

    if new_leader:
        print(f"\n{'='*60}")
        print("FAILOVER SUCCESSFUL")
        print(f"  Old Leader: {leader}")
        print(f"  New Leader: {new_leader}")
        print(f"  Total Failover Time: {failover_time:.3f} seconds")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print("FAILOVER FAILED - No new leader elected")
        print(f"  Timeout after: {failover_time:.3f} seconds")
        print(f"{'='*60}")

    # Step 5: Check final state
    time.sleep(2)  # Wait for logs to settle
    check_final_state()

    print(f"\n{'='*80}")
    print(f"Test Complete: {datetime.now().isoformat()}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
