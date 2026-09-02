#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST=/home/prekzursil/p2-g1
files='
tools/wfa_injection_gate/gate.py
tools/marketplace/pr_only_guard.py
tools/bench/nonempty.py
tools/council/protocol/hats.py
tools/council/presets/inherit.py
platform/lib/completion_predicate.py
tools/workflow_foundry/tool_requirements.py
'
for f in $files; do
  mkdir -p "$DST/$(dirname "$f")"
  rsync -a "$SRC/$f" "$DST/$f"
done
echo DELTA3-OK
