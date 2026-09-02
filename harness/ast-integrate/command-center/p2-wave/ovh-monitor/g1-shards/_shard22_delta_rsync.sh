#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
# Drop shadowing stubs on the WSL tree so packages win.
rm -f "$DST/tools/resource_guard.py" \
      "$DST/tools/testinfra.py" \
      "$DST/tools/workflow_fusion.py" \
      "$DST/tools/workflow_tournament.py" \
      "$DST/command-center/p2-wave/probes/IMP-0200/workflow_tournament.py"
dirs='
tools/plugin
tools/council
tools/resource_guard
tools/workflow_fusion
tools/testinfra
tools/marketplace
tools/workflow_foundry
tools/router
tools/bench
tools/gitcrypt-worktree
tools/lib
tools/agentspec/agentspec
command-center/workflow_tournament
command-center/library
command-center/p2-wave/seed-stage
command-center/p2-wave/probes/IMP-0252
command-center/p2-wave/probes/IMP-0200
command-center/p2-wave/probes/TST-0112
command-center/leases
'
for d in $dirs; do
  mkdir -p "$DST/$d"
  rsync -a --delete --exclude __pycache__ "$SRC/$d/" "$DST/$d/"
done
# files
rsync -a "$SRC/command-center/p2-wave/seed-stage/g1_python.py" "$DST/command-center/p2-wave/seed-stage/g1_python.py"
rsync -a "$SRC/ci/emit_hook_manifest.py" "$DST/ci/emit_hook_manifest.py"
rsync -a "$SRC/ci/gen_skills_manifest.py" "$DST/ci/gen_skills_manifest.py"
echo DELTA-RSYNC-OK
