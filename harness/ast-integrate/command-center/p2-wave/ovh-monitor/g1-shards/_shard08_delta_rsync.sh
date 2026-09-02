#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST=/home/prekzursil/p2-g1
rm -f \
  "$DST/tools/release.py" \
  "$DST/tools/test_support.py" \
  "$DST/tools/wfa_injection_gate.py" \
  "$DST/command-center/lib/overfit_detector.py" \
  "$DST/command-center/p2-wave/probes/IMP-0232/blueprint_library.py"
dirs='
tools/release
tools/test_support
tools/wfa_injection_gate
tools/detectors
tools/council/artifacts
tools/council/participants
tools/workflow_foundry
tools/plugin
tools/marketplace
tools/lib
tools/agentspec/agentspec
command-center/lib/overfit_detector
command-center/blueprint_library
command-center/adapters
command-center/phase3
command-center/p2-wave/seed-stage
'
for d in $dirs; do
  mkdir -p "$DST/$d"
  rsync -a --delete "$SRC/$d/" "$DST/$d/"
done
files='
tools/filename_gate.py
tools/pr_only_guard.py
tools/plugin/pack.py
tools/plugin/pathconv_guard.py
tools/plugin/portability_linter.py
tools/plugin/error_taxonomy.py
tools/plugin/error_taxonomy.json
tools/plugin/permission_diff.py
tools/agentspec/agentspec/cachekey.py
tools/agentspec/agentspec/canonical.py
tools/agentspec/agentspec/determinism.py
command-center/adapters/claude_adapter.py
'
for f in $files; do
  mkdir -p "$DST/$(dirname "$f")"
  rsync -a "$SRC/$f" "$DST/$f"
done
echo DELTA-RSYNC-OK
