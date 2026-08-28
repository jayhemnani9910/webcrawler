#!/usr/bin/env bash
set -euo pipefail
HERE=$(dirname "$0")
echo "Starting integration services via docker-compose..."
docker-compose -f "$PWD/docker-compose.integration.yml" up -d --build
echo "Waiting for services to initialize..."
sleep 4
# set -e would abort here on a failing test, skipping the teardown below and
# leaving the whole compose stack running. Take the exit code by hand instead.
set +e
python3 "$PWD/scripts/integration_test.py"
EXIT=$?
set -e
echo "Tearing down services..."
docker-compose -f "$PWD/docker-compose.integration.yml" down
exit $EXIT
