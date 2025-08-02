#!/bin/bash
# Generate Helm values from environment variables

# Load environment variables
[ -f ../.deploy.env ] && source ../.deploy.env

# Generate values file
cat > values.deployment.yaml << EOF
# Auto-generated Helm values from environment variables
# Generated at: $(date '+%Y-%m-%d %H:%M:%S')

# Monitor API configuration
monitor-api:
  service:
    port: ${API_PORT:-8100}
  env:
    NATS_URL: "nats://${HELM_RELEASE_NAME:-aegis-trader}-nats:${NATS_PORT:-4222}"
    NATS_KV_BUCKET: "service-registry"
    API_PORT: "${API_PORT:-8100}"
  waitForNatsPort: ${NATS_PORT:-4222}

# Monitor UI configuration
monitor-ui:
  service:
    port: ${UI_PORT:-3100}
  env:
    NEXT_PUBLIC_API_URL: "http://${HELM_RELEASE_NAME:-aegis-trader}-monitor-api:${API_PORT:-8100}"
    PORT: "${UI_PORT:-3100}"
  waitForApiPort: ${API_PORT:-8100}

# NATS configuration
nats:
  replicas: 3
  config:
    cluster:
      enabled: true
      port: 6222
      replicas: 3
    jetstream:
      enabled: true
      fileStore:
        enabled: true
        size: 10Gi
  nats:
    service:
      ports:
        client:
          port: ${NATS_PORT:-4222}
        monitor:
          port: ${NATS_MONITOR_PORT:-8222}
EOF

echo "Generated values.deployment.yaml with current environment configuration"
