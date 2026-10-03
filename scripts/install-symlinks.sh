#!/usr/bin/env bash
# install-symlinks.sh - Installs ccl symlinks in ~/.local/bin/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BIN_DIR="$PROJECT_ROOT/bin"
TARGET_DIR="$HOME/.local/bin"

mkdir -p "$TARGET_DIR"

echo "Creating symlinks in $TARGET_DIR..."

ln -sf "$BIN_DIR/ccl" "$TARGET_DIR/ccl"
ln -sf "$BIN_DIR/cci" "$TARGET_DIR/cci"                         # legacy alias → ccl
ln -sf "$BIN_DIR/claude-isvalorum" "$TARGET_DIR/claude-isvalorum"  # legacy alias → ccl
ln -sf "$BIN_DIR/claude-ollama-bridge" "$TARGET_DIR/claude-ollama-bridge"
ln -sf "$PROJECT_ROOT/scripts/search-hf.py" "$TARGET_DIR/ccl-search-hf"       # HF model search, from anywhere
ln -sf "$PROJECT_ROOT/scripts/import-model.py" "$TARGET_DIR/ccl-import-model" # import a model, from anywhere

echo "✓ $TARGET_DIR/ccl -> $BIN_DIR/ccl"
echo "✓ $TARGET_DIR/cci -> $BIN_DIR/cci (legacy)"
echo "✓ $TARGET_DIR/claude-isvalorum -> (legacy)"
echo "✓ $TARGET_DIR/claude-ollama-bridge -> $BIN_DIR/claude-ollama-bridge"
echo "✓ $TARGET_DIR/ccl-search-hf, ccl-import-model"

# Install the /find-model slash command into the isolated ccl profile
PROFILE_CMDS="$HOME/.claude-isvalorum/commands"
mkdir -p "$PROFILE_CMDS"
if [ -f "$PROJECT_ROOT/commands/find-model.md" ]; then
    ln -sf "$PROJECT_ROOT/commands/find-model.md" "$PROFILE_CMDS/find-model.md"
    echo "✓ /find-model slash command installed"
fi

echo ""
echo "✨ Symlinks installed. Run 'ccl' from any terminal (old 'cci' still works)."
