#!/bin/bash
set -euo pipefail

# Only run in remote environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Install npm dependencies
echo "Installing npm dependencies..."
npm install --prefix "$CLAUDE_PROJECT_DIR"

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --quiet -r "$CLAUDE_PROJECT_DIR/tools/requirements.txt"

# Install Smart Ralph (ralph-specum) plugin
PLUGIN_DIR="$HOME/.claude/plugins/ralph-specum"

if [ -d "$PLUGIN_DIR" ]; then
  echo "ralph-specum plugin already installed, skipping"
else
  echo "Installing Smart Ralph (ralph-specum) plugin..."
  TEMP_DIR=$(mktemp -d)
  trap "rm -rf $TEMP_DIR" EXIT
  git clone --depth=1 https://github.com/tzachbon/smart-ralph.git "$TEMP_DIR/smart-ralph"
  mkdir -p "$HOME/.claude/plugins"
  cp -R "$TEMP_DIR/smart-ralph/plugins/ralph-specum" "$PLUGIN_DIR"
  echo "ralph-specum plugin installed to $PLUGIN_DIR"
fi
