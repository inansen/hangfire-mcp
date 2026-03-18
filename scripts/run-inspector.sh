#!/bin/bash
# Hangfire MCP - Run MCP Inspector for macOS/Linux
# Reads config from .vscode/mcp.json

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_PATH="$PROJECT_ROOT/.vscode/mcp.json"

if [ ! -f "$CONFIG_PATH" ]; then
    echo "Error: mcp.json not found at $CONFIG_PATH"
    exit 1
fi

# Set environment variables from mcp.json
export DANGEROUSLY_OMIT_AUTH=true
CONN_STR=$(python3 -c "import json; c=json.load(open('$CONFIG_PATH')); print(c['servers']['hangfire-mcp']['env']['HANGFIRE_CONNECTION_STRING'])" 2>/dev/null)
if [ -n "$CONN_STR" ]; then
    export HANGFIRE_CONNECTION_STRING="$CONN_STR"
fi

COMMAND=$(python3 -c "import json; c=json.load(open('$CONFIG_PATH')); print(c['servers']['hangfire-mcp']['command'])" 2>/dev/null)
ARGS=$(python3 -c "import json,sys; c=json.load(open('$CONFIG_PATH')); args=c['servers']['hangfire-mcp']['args']; print(' '.join(a.replace('\${workspaceFolder}','$PROJECT_ROOT') for a in args))" 2>/dev/null)

echo "Starting MCP Inspector..."
echo "Dashboard: http://localhost:6274"
echo "Config: $CONFIG_PATH"
echo ""

npx @modelcontextprotocol/inspector $COMMAND $ARGS
