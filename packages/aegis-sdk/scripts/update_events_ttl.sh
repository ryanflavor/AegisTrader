#!/bin/bash
# Update EVENTS stream to enable per-message TTL

echo "Updating EVENTS stream for TTL support..."

# Since EVENTS stream has retention=limits, we can update it directly
kubectl exec -n aegis-trader aegis-trader-nats-box-84cc548785-2ct92 -- \
  bash -c 'cat <<EOF | nats req "\$JS.API.STREAM.UPDATE.EVENTS" -
{
  "config": {
    "allow_msg_ttl": true
  }
}
EOF'

echo ""
echo "Verifying EVENTS stream TTL configuration:"
kubectl exec -n aegis-trader aegis-trader-nats-box-84cc548785-2ct92 -- \
  nats stream info EVENTS -j | jq '.config | {name, retention, allow_msg_ttl}'
