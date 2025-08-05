#!/bin/bash
# Enable per-message TTL on K8s NATS streams

echo "Enabling per-message TTL on K8s NATS streams..."

# Function to update stream to enable TTL
update_stream_ttl() {
    local stream_name=$1
    echo "Updating stream: $stream_name"

    # Get current stream config
    kubectl exec -n aegis-trader aegis-trader-nats-box-84cc548785-2ct92 -- \
        nats stream info "$stream_name" -j > /tmp/stream_config.json

    # Update config to enable TTL
    jq '.config.allow_msg_ttl = true' /tmp/stream_config.json > /tmp/stream_config_updated.json

    # Update the stream via NATS API
    kubectl exec -n aegis-trader aegis-trader-nats-box-84cc548785-2ct92 -- \
        nats stream edit "$stream_name" --config=/dev/stdin < /tmp/stream_config_updated.json
}

# Update COMMANDS stream
kubectl exec -n aegis-trader aegis-trader-nats-box-84cc548785-2ct92 -- \
    nats stream edit COMMANDS --config='{"allow_msg_ttl": true}'

# Update EVENTS stream
kubectl exec -n aegis-trader aegis-trader-nats-box-84cc548785-2ct92 -- \
    nats stream edit EVENTS --config='{"allow_msg_ttl": true}'

echo "✅ TTL enabled on K8s NATS streams"

# Verify the changes
echo ""
echo "Verifying configuration:"
kubectl exec -n aegis-trader aegis-trader-nats-box-84cc548785-2ct92 -- \
    nats stream info COMMANDS -j | jq '.config | {name, allow_msg_ttl}'
kubectl exec -n aegis-trader aegis-trader-nats-box-84cc548785-2ct92 -- \
    nats stream info EVENTS -j | jq '.config | {name, allow_msg_ttl}'
