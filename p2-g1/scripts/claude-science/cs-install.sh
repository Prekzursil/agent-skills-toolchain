#!/bin/bash
set -uo pipefail

echo "=== deps check ==="
for c in curl bwrap socat jq; do
  if command -v "$c" >/dev/null 2>&1; then
    echo "$c: present ($($c --version 2>/dev/null | head -1))"
  else
    echo "$c: MISSING"
  fi
done
echo

echo "=== install claude-science (user-space, no sudo) ==="
if [ -s /tmp/cs-bootstrap.sh ]; then
  bash /tmp/cs-bootstrap.sh
else
  curl -fsSL "https://claude.ai/install-claude-science.sh" | bash
fi
echo

echo "=== verify install ==="
ls -la "$HOME/.local/bin/claude-science" 2>&1 || echo "binary not found"
echo "--- version ---"
"$HOME/.local/bin/claude-science" --version 2>&1 | head -5 || echo "(version check failed)"
echo "--- help (learn real subcommands/flags) ---"
"$HOME/.local/bin/claude-science" --help 2>&1 | head -40 || true
