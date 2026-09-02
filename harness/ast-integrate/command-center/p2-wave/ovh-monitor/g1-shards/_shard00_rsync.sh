#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
mkdir -p "$DST"
dirs='
tools/marketplace
tools/plugin
tools/council
tools/selfimprove
tools/headroom_guard
tools/mcp_process_guard
tools/blueprint_library
tools/event-ledger
tools/monitorcore
tools/agentspec
tools/agentspec-js
tools/workflow_foundry
tools/agentrail
release/platforms/windows
lib
agentspec
command-center/schema
command-center/adversarial
command-center/audit
command-center/receipts
command-center/confirmation
command-center/phase3
command-center/wfa
command-center/foundry
command-center/research
command-center/synthesis
command-center/p2-wave/_measure_one_delivered.py
command-center/p2-wave/seed-stage
'
for d in $dirs; do
  mkdir -p "$DST/$(dirname "$d")"
  if [ -e "$SRC/$d" ]; then
    rsync -a "$SRC/$d" "$DST/$(dirname "$d")/"
  fi
done
while IFS= read -r uid; do
  [ -z "$uid" ] && continue
  srcp="$SRC/command-center/p2-wave/probes/$uid"
  dstp="$DST/command-center/p2-wave/probes/$uid"
  if [ -d "$srcp" ]; then
    mkdir -p "$dstp"
    rsync -a "$srcp/" "$dstp/"
  fi
done < "$SRC/command-center/p2-wave/ovh-monitor/g1-shards/shard-00.txt"
echo RSYNC-OK
du -sh "$DST"

