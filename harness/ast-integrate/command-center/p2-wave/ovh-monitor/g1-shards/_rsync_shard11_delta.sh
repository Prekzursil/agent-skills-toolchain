#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
trees='
tools/plugin
tools/marketplace
tools/council
tools/foundry
tools/blueprints
tools/agentspec
tools/workflows
tools/bench
tools/testinfra
tools/fusion.py
tools/router/index_build.py
tools/command-center/output_schema_gate.py
command-center/lib
command-center/bench
command-center/foundry
command-center/confirmation
command-center/design
command-center/receipts
command-center/p2-wave/probes
command-center/phase3/A8
command-center/p2-wave/_measure_one_delivered.py
command-center/p2-wave/seed-stage
'
for t in $trees; do
  if [ -d "$SRC/$t" ]; then
    mkdir -p "$DST/$t"
    extra=""
    case "$t" in
      command-center/lib|command-center/phase3/A8) extra="--delete" ;;
    esac
    rsync -a $extra --exclude __pycache__ --exclude '*.pyc' "$SRC/$t/" "$DST/$t/"
  elif [ -f "$SRC/$t" ]; then
    mkdir -p "$DST/$(dirname "$t")"
    rsync -a "$SRC/$t" "$DST/$t"
  fi
done
echo RSYNC-SHARD11-DELTA-OK
