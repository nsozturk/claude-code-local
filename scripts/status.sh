#!/usr/bin/env bash
# status.sh - Displays status of ccl bridge, Ollama daemon, and active memory usage

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(cd -P "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"

echo "=== 🔌 CCL Bridge Status ==="
"$PROJECT_ROOT/bin/claude-ollama-bridge" status
echo ""
echo "=== 🦙 Ollama Server Status ==="
if curl -s --max-time 1 "http://127.0.0.1:11434/api/tags" > /dev/null 2>&1; then
    echo "Ollama is running on http://127.0.0.1:11434"
else
    echo "Ollama is NOT running"
fi
echo ""
echo "=== ⚡ Active Models in RAM/VRAM ==="
ollama ps
