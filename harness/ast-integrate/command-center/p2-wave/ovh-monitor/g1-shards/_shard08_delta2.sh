#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST=/home/prekzursil/p2-g1
files='
tools/release/bundle_secret_scan.py
platform/lib/completion_predicate.py
tools/workflow_foundry/tool_requirements.py
command-center/lib/overfit_detector/detector.py
tools/council/participants/select_auto.py
tools/detectors/two_state.py
tools/detectors/census.py
tools/marketplace/filename_gate.py
tools/wfa_injection_gate/gate.py
tools/bench/nonempty.py
tools/plugin/pathconv_guard.py
tools/plugin/error_taxonomy.py
command-center/adapters/claude_adapter.py
tools/council/protocol/hats.py
tools/council/presets/inherit.py
tools/filename_gate.py
'
for f in $files; do
  mkdir -p "$DST/$(dirname "$f")"
  rsync -a "$SRC/$f" "$DST/$f"
done
echo DELTA2-OK
