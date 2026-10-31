#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
if claude-science status 2>/dev/null | grep -q '"running": true'; then
  echo "Claude Science already running."
else
  echo "Starting Claude Science daemon..."
  read -ra cs_extra <<<"$(cat "$HOME/.cs-serve-extra" 2>/dev/null || true)"
  claude-science serve --no-browser --detached --no-auto-update "${cs_extra[@]}" 2>&1 | tail -3
  sleep 5
fi
claude-science status 2>&1 | grep -E '"running"|"pid"|"port"'
echo "login URL:"
claude-science url 2>&1 | head -1
