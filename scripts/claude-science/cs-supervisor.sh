#!/bin/bash
# cs-supervisor — in-WSL self-heal for Claude Science (defense-in-depth alongside the Windows
# watchdog). Launched by /etc/wsl.conf `[boot] command=` at VM start (installer wires it), or run
# manually. Ensures CS up the instant WSL boots, then latency-probes + self-recovers with a
# heartbeat file. No systemd (avoids the systemd-resolved/DNS blast-radius on this distro).
# Wedge = socket accepts but HTTP is slow/silent (WSL frozen under host-RAM pressure).
export PATH="$HOME/.local/bin:$PATH"
# Config seam. Fail LOUD if a partial deploy dropped it: without cs-lib.sh the helpers below
# are undefined and every $CS_* is empty, which would silently target the wrong paths.
_cs_lib="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cs-lib.sh"
[ -r "$_cs_lib" ] || { echo "!!! cs-lib.sh missing beside $0 - re-run install.ps1 (it deploys cs-lib.sh + cs.conf)" >&2; exit 1; }
# shellcheck source=cs-lib.sh
. "$_cs_lib"
URL="$CS_URL"
DD="$(cs_data_dir)"
HB="$DD/supervisor.heartbeat"
LOG="$DD/supervisor.log"
SLOWSEC=$(( CS_SLOW_MS / 1000 ))   # from cs.conf, so the wedge threshold matches cs-lib.ps1
SLOWSTRIKES=3      # consecutive SLOW/WEDGE (~90s) => recover
slow=0
mkdir -p "$DD" 2>/dev/null

log() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }
# rotate own log if > 5MB
[ -f "$LOG" ] && [ "$(stat -c%s "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ] && mv -f "$LOG" "$LOG.1"

# single-instance: don't stack supervisors if [boot] fires oddly or it's run twice
exec 8>"$DD/.supervisor.lock"
if command -v flock >/dev/null 2>&1 && ! flock -n 8; then log "another supervisor holds the lock - exiting"; exit 0; fi

log "supervisor start (pid $$)"
cs-start >/dev/null 2>&1 || true    # ensure up the instant WSL boots (closes the boot gap)

while true; do
  # %{http_code} %{time_total}; -m 8 hard cap. A hang yields http=000, time~8.
  r=$(curl -s -o /dev/null -m 8 -w '%{http_code} %{time_total}' "$URL" 2>/dev/null)
  http=${r%% *}; t=${r##* }
  if [ -z "$http" ] || [ "$http" = "000" ]; then
    if timeout 2 bash -c "exec 3<>/dev/tcp/$CS_HOST/$CS_PORT" 2>/dev/null; then state=WEDGE; else state=DOWN; fi
  elif [ "$(awk -v x="$t" -v s="$SLOWSEC" 'BEGIN{print (x>=s)?1:0}')" = "1" ]; then
    state=SLOW
  else
    state=HEALTHY
  fi
  echo "$(date -u +%FT%TZ) state=$state http=$http t=${t}s" > "$HB"   # mtime = liveness signal
  case "$state" in
    HEALTHY) slow=0 ;;
    SLOW|WEDGE) slow=$((slow + 1)); if [ "$slow" -ge "$SLOWSTRIKES" ]; then log "wedge (state=$state t=${t}s) -> cs-recover"; cs-recover >/dev/null 2>&1; slow=0; fi ;;
    DOWN) log "down -> cs-start"; cs-start >/dev/null 2>&1 || true; slow=0 ;;
  esac
  sleep 30
done
