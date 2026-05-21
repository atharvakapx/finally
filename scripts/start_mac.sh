#!/usr/bin/env bash
set -e
IMAGE=finally
CONTAINER=finally

# Build if image doesn't exist or --build flag passed
if [[ "$1" == "--build" ]] || ! docker image inspect "$IMAGE" &>/dev/null; then
  echo "Building $IMAGE image..."
  docker build -t "$IMAGE" "$(dirname "$0")/.."
fi

# Stop existing container if running
docker rm -f "$CONTAINER" 2>/dev/null || true

# Run
docker run -d \
  --name "$CONTAINER" \
  -v "$PWD/db:/app/db" \
  -p 8000:8000 \
  --env-file .env \
  "$IMAGE"

echo "FinAlly running at http://localhost:8000"
