#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
copy() {
  mkdir -p "$DST/$(dirname "$1")"
  cp -a "$SRC/$1" "$DST/$1"
  echo copied "$1"
}
copy council/antifail/unanimity.py
copy tools/council/phases.py
copy tools/foundry/candidate_registry.py
copy tools/workflow_foundry/unknown_probe.py
copy hooks/_shared/use_vs_mention.py
echo COPY-OK
