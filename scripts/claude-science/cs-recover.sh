#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
DD="$HOME/.claude-science"

echo "=== 1) crash cause (tail of newest server log) ==="
newest=$(ls -t "$DD"/logs/server-*.log 2>/dev/null | head -1)
[ -n "$newest" ] && tail -15 "$newest" || echo "(no server log)"
echo

echo "=== 2) force-kill any stuck claude-science (incl. the hung relaunch's child) ==="
pkill -9 -f 'claude-science' 2>/dev/null && echo "killed lingering process(es)" || echo "none running"
sleep 2

echo "=== 3) clear stale locks/sockets (daemon is confirmed down) ==="
rm -f "$DD/daemon.sock" "$DD/operon.lock" 2>/dev/null
rm -rf "$DD"/sbx-bind-src/sock-* 2>/dev/null
echo "cleared daemon.sock, operon.lock, stale sandbox sockets"
echo

echo "=== 4) clean start (detached, pinned) ==="
CS_EXTRA=$(cat "$HOME/.cs-serve-extra" 2>/dev/null || true)
claude-science serve --no-browser --detached --no-auto-update $CS_EXTRA 2>&1 | tail -5
sleep 7
echo

echo "=== 5) verify ==="
claude-science status 2>&1 | grep -E '"running"|"pid"|"port"' || echo "!!! STILL DOWN"
echo

echo "=== 6) fresh login URL ==="
claude-science url 2>&1 | head -2
