#!/bin/bash
# MiniMax ACP Agent Launcher
# This script launches the MiniMax ACP Agent for JetBrains integration

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH="${PYTHON_PATH:-python3}"

exec "$PYTHON_PATH" "$SCRIPT_DIR/src/agent.py"
