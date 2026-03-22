#!/bin/bash
# Fix openclaw.json ownership after sandbox restart
# Must be run from host machine, not inside sandbox
# See: docs/troubleshooting/startup-and-failure-point-map.md — Maintenance Step 1

CONTAINER=$(docker ps --format "{{.ID}}" --filter name=openshell-cluster | head -1)
if [ -z "$CONTAINER" ]; then
  echo "ERROR: openshell-cluster container not found. Is Docker Desktop running?"
  exit 1
fi

echo "Container: $CONTAINER"
docker exec "$CONTAINER" kubectl exec -n openshell nemoclaw-assistant -- chmod 644 /sandbox/.openclaw/openclaw.json
docker exec "$CONTAINER" kubectl exec -n openshell nemoclaw-assistant -- chown sandbox:sandbox /sandbox/.openclaw/openclaw.json
docker exec "$CONTAINER" kubectl exec -n openshell nemoclaw-assistant -- ls -la /sandbox/.openclaw/openclaw.json
echo "Done. Now run: nemoclaw nemoclaw-assistant connect"
echo "Then inside sandbox: openclaw models set inference/openai/gpt-4o-mini"
