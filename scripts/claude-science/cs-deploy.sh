#!/bin/bash
# Install the WSL cs-* commands to ~/.local/bin, bring the daemon up pinned, take first backup.
export PATH="$HOME/.local/bin:$PATH"
SRC=/mnt/c/Users/Prekzursil/source/agent-skills-toolchain/scripts/claude-science
mkdir -p "$HOME/.local/bin"
for f in cs-backup cs-maintain cs-start cs-recover; do
  tr -d '\r' < "$SRC/$f.sh" > "$HOME/.local/bin/$f" && chmod +x "$HOME/.local/bin/$f" && echo "installed $f"
done
echo "=== bring daemon up (pinned) ==="
cs-start 2>&1 | grep -vE 'nonce' | head -8
echo "=== FIRST BACKUP ==="
cs-backup
