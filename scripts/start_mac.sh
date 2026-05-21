#!/bin/bash
set -e

IMAGE_NAME="finally"
CONTAINER_NAME="finally"
PORT=8000

# Resolve project root (one level up from this script)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Ensure .env exists (docker --env-file requires it)
if [[ ! -f .env ]]; then
    if [[ -f .env.example ]]; then
        echo "No .env found — copying from .env.example"
        cp .env.example .env
    else
        echo "Warning: no .env or .env.example found; creating empty .env"
        : > .env
    fi
fi

# Ensure db directory exists for the bind mount
mkdir -p db

# Stop existing container if running
if docker ps -a -q -f name="^${CONTAINER_NAME}$" | grep -q .; then
    echo "Stopping existing container..."
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
fi

# Build if image doesn't exist or --build flag passed
if [[ "$1" == "--build" ]] || ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
    echo "Building Docker image..."
    docker build -t "$IMAGE_NAME" .
fi

# Run container
echo "Starting FinAlly..."
docker run -d \
    --name "$CONTAINER_NAME" \
    -v "$PROJECT_ROOT/db:/app/db" \
    -p "$PORT:8000" \
    --env-file .env \
    "$IMAGE_NAME"

echo ""
echo "FinAlly is running at http://localhost:$PORT"
echo "To stop: ./scripts/stop_mac.sh"

# Open browser (macOS)
if command -v open &>/dev/null; then
    sleep 2 && open "http://localhost:$PORT" &
fi
