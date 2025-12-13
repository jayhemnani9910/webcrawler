#!/usr/bin/env bash
set -euo pipefail
HERE=$(dirname "$0")
echo "Starting integration services via docker-compose..."
docker-compose -f "$PWD/docker-compose.integration.yml" up -d --build
echo "Waiting for services to initialize..."
sleep 4
python3 "$PWD/scripts/integration_test.py"
EXIT=$?
echo "Tearing down services..."
docker-compose -f "$PWD/docker-compose.integration.yml" down
exit $EXIT
