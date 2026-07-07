#!/bin/bash
# cs-recover — force-recover a DOWN or WEDGED Claude Science daemon.
# Fixes vs the old version: (0) safety-backup first; (2) graceful stop then a SCOPED kill of only
# the daemon child + recorded pid (NOT a broad `pkill -9 -f claude-science`, which SIGKILLs any
# editor/grep/log tailing the path and can corrupt the DB mid-write); (4) wait for the port to
# actually free before restarting.
export PATH="$HOME/.local/bin:$PATH"
DD="$HOME/.claude-science"

# serialize: the Windows watchdog and the in-WSL supervisor must never recover at the same time
mkdir -p "$DD" 2>/dev/null
exec 9>"$DD/.recover.lock"
if command -v flock >/dev/null 2>&1 && ! flock -n 9; then echo "another cs-recover is already running - skipping"; exit 0; fi

echo "=== 0) safety backup before destructive recover ==="
if command -v cs-backup >/dev/null 2>&1; then cs-backup 2>&1 | tail -2 || echo "(backup failed — continuing recover)"; else echo "(cs-backup not on PATH — skipping backup)"; fi

echo "=== 1) crash cause (tail of newest server log) ==="
newest=$(ls -t "$DD"/logs/server-*.log 2>/dev/null | head -1)
[ -n "$newest" ] && tail -12 "$newest" || echo "(no server log)"

echo "=== 2) graceful stop, then SCOPED kill ==="
pid=$(claude-science status 2>/dev/null | grep -oE '"pid":[[:space:]]*[0-9]+' | grep -oE '[0-9]+' | head -1)
timeout 12 claude-science stop >/dev/null 2>&1 || true
sleep 1
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
  echo "graceful stop timed out; TERM->KILL pid $pid (+ children)"
  pkill -TERM -P "$pid" 2>/dev/null; kill -TERM "$pid" 2>/dev/null; sleep 2
  kill -9 "$pid" 2>/dev/null || true
fi
# last resort, PRECISELY scoped to the detached daemon child only (not any 'claude-science' string)
pkill -9 -f 'claude-science serve .*--_daemon-child' 2>/dev/null || true
sleep 1

echo "=== 3) clear stale locks/sockets (daemon confirmed down) ==="
rm -f "$DD/daemon.sock" "$DD/operon.lock" 2>/dev/null
rm -rf "$DD"/sbx-bind-src/sock-* 2>/dev/null
echo "cleared daemon.sock, operon.lock, stale sandbox sockets"

echo "=== 4) wait for port 8000 to free, then clean start (pinned) ==="
for i in 1 2 3 4 5 6; do
  if (exec 3<>/dev/tcp/127.0.0.1/8000) 2>/dev/null; then exec 3>&- 2>/dev/null; echo "port still busy, waiting ($i)"; sleep 1; else break; fi
done
CS_EXTRA=$(cat "$HOME/.cs-serve-extra" 2>/dev/null || true)
claude-science serve --no-browser --detached --no-auto-update $CS_EXTRA 2>&1 | tail -3
sleep 6

echo "=== 5) verify ==="
claude-science status 2>&1 | grep -E '"running"|"pid"|"port"' || echo "!!! STILL DOWN"

echo "=== 6) fresh login URL ==="
claude-science url 2>&1 | head -2
