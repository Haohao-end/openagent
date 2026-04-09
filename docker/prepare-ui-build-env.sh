#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
API_ENV_FILE="${1:-$PROJECT_ROOT/api/.env}"
OUTPUT_FILE="${2:-$SCRIPT_DIR/.ui-build.env}"

if [ ! -f "$API_ENV_FILE" ]; then
  echo "ERROR: missing API env file: $API_ENV_FILE" >&2
  exit 1
fi

vite_api_prefix="$(python3 - "$API_ENV_FILE" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
value = None

for raw_line in path.read_text(encoding='utf-8').splitlines():
    line = raw_line.strip()
    if not line or line.startswith('#'):
        continue
    if '=' not in line:
        continue
    key, val = line.split('=', 1)
    if key.strip() != 'VITE_API_PREFIX':
        continue
    value = val.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    break

if not value:
    raise SystemExit('')

print(value)
PY
)"

if [ -z "$vite_api_prefix" ]; then
  echo "ERROR: VITE_API_PREFIX is required in $API_ENV_FILE" >&2
  exit 1
fi

cat > "$OUTPUT_FILE" <<EOF
# Generated from $API_ENV_FILE
VITE_API_PREFIX=$vite_api_prefix
EOF

echo "Generated frontend build env: $OUTPUT_FILE"

