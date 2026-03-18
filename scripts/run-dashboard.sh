#!/bin/bash
# Hangfire MCP - Setup & Dashboard runner for macOS/Linux
# Reads config from .vscode/mcp.json

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_PATH="$PROJECT_ROOT/.vscode/mcp.json"

echo ""
echo "🔥 Hangfire Dashboard"
echo ""

# Get connection string from mcp.json
if [ -f "$CONFIG_PATH" ]; then
    CONN_STR=$(python3 -c "import json; c=json.load(open('$CONFIG_PATH')); print(c['servers']['hangfire-mcp']['env']['HANGFIRE_CONNECTION_STRING'])" 2>/dev/null)
    if [ -n "$CONN_STR" ]; then
        export HANGFIRE_CONNECTION_STRING="$CONN_STR"
        echo "✓ Loaded connection string from mcp.json"
    fi
fi

if [ -z "$HANGFIRE_CONNECTION_STRING" ]; then
    echo "⚠ HANGFIRE_CONNECTION_STRING not found"
    echo "Set it in .vscode/mcp.json or as an environment variable"
    exit 1
fi

HOST="${1:-127.0.0.1}"
PORT="${2:-8080}"

echo ""
echo "Starting dashboard at http://${HOST}:${PORT}"
echo "Press Ctrl+C to stop"
echo ""

cd "$PROJECT_ROOT"
python3 -m uvicorn hangfire_mcp.dashboard:app --host "$HOST" --port "$PORT"
