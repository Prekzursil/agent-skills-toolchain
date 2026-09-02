#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
dirs='
tools/marketplace
tools/workflow_fusion
tools/workflow_forge
tools/council
tools/router
tools/hud
tools/test_discovery
tools/sync
tools/agentspec/agentspec
tools/command-center
command-center/foundry/revocation
platform/blueprints
command-center/p2-wave/seed-stage
hooks/_dispatch
command-center/foundry/revocation
'
for d in $dirs; do
  mkdir -p "$DST/$d"
  rsync -a --exclude '__pycache__' "$SRC/$d/" "$DST/$d/"
done
# files that may have been removed on the source (stubs replaced by packages)
for f in tools/workflow_fusion.py tools/hud.py tools/sync.py tools/test_discovery.py; do
  rm -f "$DST/$f"
done
echo DELTA-RSYNC-OK
find "$DST/tools/workflow_fusion" "$DST/tools/hud" "$DST/platform/blueprints" -maxdepth 2 -type f | wc -l
