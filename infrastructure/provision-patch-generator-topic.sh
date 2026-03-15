#!/usr/bin/env bash
# provision-patch-generator-topic.sh
# Creates the patch-generator-input Service Bus topic and subscription.
# Run once before starting the NLP Pipeline consumer.

set -euo pipefail

RG="sentinel-d-rg"
NS="sentinel-d-bus"
TOPIC="patch-generator-input"
SUB="patch-generator-sub"

echo "Creating Service Bus topic: $TOPIC"
az servicebus topic create \
  --resource-group "$RG" \
  --namespace-name "$NS" \
  --name "$TOPIC" \
  --output table

echo "Creating subscription: $SUB"
az servicebus topic subscription create \
  --resource-group "$RG" \
  --namespace-name "$NS" \
  --topic-name "$TOPIC" \
  --name "$SUB" \
  --max-delivery-count 10 \
  --lock-duration "PT5M" \
  --dead-lettering-on-message-expiration true \
  --output table

echo "Done — patch-generator-input topic and subscription created."
echo ""
echo "Add to .env:"
echo "  PATCH_GENERATOR_TOPIC=patch-generator-input"