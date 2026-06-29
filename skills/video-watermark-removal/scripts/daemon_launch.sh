#!/usr/bin/env bash
# Detached daemon wrapper. Run via a fast-returning foreground call so it survives
# the launching wsl.exe bridge being killed (WSL2 keeps VM processes alive):
#   wsl.exe -e bash -lc 'cd <job> && BASE=/mnt/c/.../job setsid nohup bash <skill>/scripts/daemon_launch.sh > batch_daemon.log 2>&1 < /dev/null & disown'
# Then watch batch_daemon.log + batch_daemon.done with a PERSISTENT Monitor
# (no wsl.exe inside the monitor loop). Writes batch_daemon.done when finished.
set -u
: "${BASE:?set BASE=/mnt/c/.../job-root}"
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DONE="$BASE/batch_daemon.done"
rm -f "$DONE"
echo "=== daemon start $(date) ==="
BASE="$BASE" bash "$HERE/retry_until_complete.sh"
rc=$?
echo "=== daemon finished rc=$rc $(date) ==="
echo "DAEMON_EXIT=$rc $(date)" > "$DONE"
