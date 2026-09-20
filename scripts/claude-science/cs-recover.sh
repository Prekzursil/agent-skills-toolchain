#!/bin/bash
# cs-recover — force-recover a DOWN or WEDGED Claude Science daemon.
# Fixes vs the old version: (0) safety-backup first; (2) graceful stop then a SCOPED kill of only
# the daemon child + recorded pid (NOT a broad `pkill -9 -f claude-science`, which SIGKILLs any
# editor/grep/log tailing the path and can corrupt the DB mid-write); (4) wait for the port to
# actually free before restarting.
export PATH="$HOME/.local/bin:$PATH"
# Config seam. Fail LOUD if a partial deploy dropped it: without cs-lib.sh the helpers below
# are undefined and every $CS_* is empty, which would silently target the wrong paths.
_cs_lib="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cs-lib.sh"
[ -r "$_cs_lib" ] || { echo "!!! cs-lib.sh missing beside $0 - re-run install.ps1 (it deploys cs-lib.sh + cs.conf)" >&2; exit 1; }
# shellcheck source=cs-lib.sh
. "$_cs_lib"
DD="$(cs_data_dir)"

# serialize: the Windows watchdog and the in-WSL supervisor must never recover at the same time
mkdir -p "$DD" 2>/dev/null
exec 9>"$DD/.recover.lock"
if command -v flock >/dev/null 2>&1 && ! flock -n 9; then echo "another cs-recover is already running - skipping"; exit 0; fi

echo "=== 0) safety backup before destructive recover ==="
if command -v cs-backup >/dev/null 2>&1; then cs-backup 2>&1 | tail -2 || echo "(backup failed — continuing recover)"; else echo "(cs-backup not on PATH — skipping backup)"; fi

echo "=== 1) crash cause (tail of newest server log) ==="
newest=$(find "$DD"/logs -maxdepth 1 -name 'server-*.log' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
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

echo "=== 4) wait for port $CS_PORT to free, then clean start (pinned) ==="
for i in 1 2 3 4 5 6; do
  if (exec 3<>/dev/tcp/"$CS_HOST"/"$CS_PORT") 2>/dev/null; then exec 3>&- 2>/dev/null; echo "port still busy, waiting ($i)"; sleep 1; else break; fi
done
# Model bridge (owner-directed 2026-09-20): same optional env injection as
# cs-start.sh; written by cs-model, absent = native Anthropic.
if [ -f "$HOME/.claude-science/daemon-env" ]; then
  # shellcheck disable=SC1091
  . "$HOME/.claude-science/daemon-env"
  echo "[cs-recover] model bridge active: ${CS_MODEL_BRIDGE:-unspecified}"
fi
read -ra cs_extra <<<"$(cat "$HOME/.cs-serve-extra" 2>/dev/null || true)"
claude-science serve --no-browser --detached --no-auto-update "${cs_extra[@]}" 2>&1 | tail -3
sleep 6

echo "=== 5) verify ==="
claude-science status 2>&1 | grep -E '"running"|"pid"|"port"' || echo "!!! STILL DOWN"

echo "=== 6) fresh login URL ==="
claude-science url 2>&1 | head -2
