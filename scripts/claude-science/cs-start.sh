#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
# Model bridge (owner-directed 2026-09-20): cs-model writes an optional env
# file that redirects the daemon's Anthropic API calls at a GLM coding-plan
# endpoint. Absent file = native Anthropic (the revert path is literally
# `cs-model anthropic && cs fix`). Never hardcode keys here — the file is
# generated per-swap from the live env by cs-model.
if [ -f "$HOME/.claude-science/daemon-env" ]; then
  # shellcheck disable=SC1091
  . "$HOME/.claude-science/daemon-env"
  echo "[cs-start] model bridge active: ${CS_MODEL_BRIDGE:-unspecified} (ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-unset})"
fi
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
