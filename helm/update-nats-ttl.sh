#!/bin/bash
# Script to update NATS with TTL support

echo "🚀 Updating NATS with per-message TTL support..."

# Check current values
echo -e "\n📋 Current deployment values:"
helm get values aegis-trader -n aegis-trader

# Upgrade with TTL enabled
echo -e "\n🔧 Applying TTL configuration..."
helm upgrade aegis-trader . \
  -n aegis-trader \
  -f values.yaml \
  -f values.ttl-enabled.yaml \
  --wait

echo -e "\n✅ Update complete! Checking NATS pods status..."
kubectl get pods -n aegis-trader -l app.kubernetes.io/name=nats

echo -e "\n📊 Checking NATS ConfigMap for TTL setting..."
kubectl get configmap aegis-trader-nats-config -n aegis-trader -o yaml | grep -A5 -B5 "allow_msg_ttl"

echo -e "\n🧪 To test TTL functionality, run:"
echo "uv run python ../test_nats_kv_ttl.py"
