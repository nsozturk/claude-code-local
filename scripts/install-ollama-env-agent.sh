#!/usr/bin/env bash
# install-ollama-env-agent.sh — make the ccl --tune SERVER settings survive reboot.
# Installs a per-user LaunchAgent that runs apply-ollama-env.py at login.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPLY="$SCRIPT_DIR/apply-ollama-env.py"
LABEL="dev.ccl.ollama-env"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PYTHON="$(command -v python3)"

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$APPLY</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>StandardOutPath</key><string>$HOME/.claude-isvalorum/ollama-env-agent.log</string>
    <key>StandardErrorPath</key><string>$HOME/.claude-isvalorum/ollama-env-agent.log</string>
</dict>
</plist>
PLISTEOF

# (re)load it
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "✓ LaunchAgent installed: $PLIST"
echo "  runs $APPLY at every login"
echo "  remove with: launchctl unload '$PLIST' && rm '$PLIST'"
