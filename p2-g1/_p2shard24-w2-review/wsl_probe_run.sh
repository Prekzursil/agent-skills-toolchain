#!/bin/bash
# POSIX-lane probe re-run for shard-24 reviewer (r2). Runs INSIDE WSL.
# usage: wsl_probe_run.sh <probe1.py> <probe2.py>
cd /mnt/c/Users/Prekzursil/p2-g1 || exit 97
export PYTHONDONTWRITEBYTECODE=1
export AST_INTEGRATE_ROOT="/mnt/c/Users/Prekzursil/p2-g1"
export PYTHONPATH="/mnt/c/Users/Prekzursil/p2-g1/command-center/p2-wave/seed-stage:/mnt/c/Users/Prekzursil/p2-g1:/mnt/c/Users/Prekzursil/p2-g1/tools:/mnt/c/Users/Prekzursil/p2-g1/tools/measure-guard:/mnt/c/Users/Prekzursil/p2-g1/platform/lib:/mnt/c/Users/Prekzursil/p2-g1/tools/agentspec"
for cmd in "$@"; do
  echo "### RUN: $cmd"
  timeout 900 python3 -B "$cmd"
  echo "### RC=$? for $cmd"
done
