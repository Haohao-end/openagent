#!/bin/bash

# OpenAgent Docker quick start script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yaml"
ENV_FILE="$PROJECT_ROOT/api/.env"
ENV_EXAMPLE="$PROJECT_ROOT/api/.env.example"
UI_BUILD_ENV_FILE="$SCRIPT_DIR/.ui-build.env"
PREPARE_UI_ENV_SCRIPT="$SCRIPT_DIR/prepare-ui-build-env.sh"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose v2 is not available"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  if [ ! -f "$ENV_EXAMPLE" ]; then
    echo "ERROR: missing $ENV_FILE and $ENV_EXAMPLE"
    exit 1
  fi
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  echo "Created $ENV_FILE from $ENV_EXAMPLE"
fi

if [ ! -x "$PREPARE_UI_ENV_SCRIPT" ]; then
  chmod +x "$PREPARE_UI_ENV_SCRIPT"
fi

"$PREPARE_UI_ENV_SCRIPT" "$ENV_FILE" "$UI_BUILD_ENV_FILE"

if ! docker compose --env-file "$ENV_FILE" --env-file "$UI_BUILD_ENV_FILE" -f "$COMPOSE_FILE" config --quiet; then
  echo "ERROR: docker-compose.yaml is invalid"
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"
# shellcheck disable=SC1090
source "$UI_BUILD_ENV_FILE"

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

docker compose --env-file "$ENV_FILE" --env-file "$UI_BUILD_ENV_FILE" -f "$COMPOSE_FILE" build
docker compose --env-file "$ENV_FILE" --env-file "$UI_BUILD_ENV_FILE" -f "$COMPOSE_FILE" up -d

echo ""
docker compose --env-file "$ENV_FILE" --env-file "$UI_BUILD_ENV_FILE" -f "$COMPOSE_FILE" ps

echo ""
echo "Use these commands:"
echo "  ./prepare-ui-build-env.sh ../api/.env ./.ui-build.env"
echo "  docker compose --env-file ../api/.env --env-file ./.ui-build.env -f docker-compose.yaml logs -f [service]"
echo "  docker compose --env-file ../api/.env --env-file ./.ui-build.env -f docker-compose.yaml down"
