#!/bin/bash

# OpenAgent Docker quick start script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yaml"
ENV_FILE="$PROJECT_ROOT/api/.env"
ENV_EXAMPLE="$PROJECT_ROOT/api/.env.example"
DOCKER_ENV_FILE="$SCRIPT_DIR/.env"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose v2 is not available"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: missing $ENV_FILE"
  echo "Copy $ENV_EXAMPLE to $ENV_FILE and set VITE_API_PREFIX before starting Docker services."
  exit 1
fi

if ! docker compose -f "$COMPOSE_FILE" config --quiet; then
  echo "ERROR: docker-compose.yaml is invalid"
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"
if [ -f "$DOCKER_ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$DOCKER_ENV_FILE"
fi

echo "Frontend:   http://localhost:${UI_PORT:-3000}"
echo "API:        http://localhost:${API_PORT:-5001}"
echo "Nginx HTTP: http://localhost:${NGINX_HTTP_PORT:-80}"
echo "Nginx HTTPS:https://localhost:${NGINX_HTTPS_PORT:-443}"
echo "UI build API prefix: ${VITE_API_PREFIX}"

read -r -p "Start services now? [Y/n] " REPLY
if [[ ! "$REPLY" =~ ^[Yy]$ ]] && [[ -n "$REPLY" ]]; then
  echo "Canceled"
  exit 0
fi

docker compose -f "$COMPOSE_FILE" build
docker compose -f "$COMPOSE_FILE" up -d

echo ""
docker compose -f "$COMPOSE_FILE" ps

echo ""
echo "Use these commands:"
echo "  docker compose -f docker-compose.yaml logs -f [service]"
echo "  docker compose -f docker-compose.yaml down"
