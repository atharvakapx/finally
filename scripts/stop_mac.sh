#!/bin/bash
CONTAINER_NAME="finally"

if docker ps -a -q -f name="^${CONTAINER_NAME}$" | grep -q .; then
    echo "Stopping FinAlly..."
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
    echo "Stopped."
else
    echo "FinAlly is not running."
fi
