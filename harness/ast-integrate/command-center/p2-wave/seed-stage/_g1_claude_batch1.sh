#!/usr/bin/env bash
set -uo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
for u in ADV-0010 ARC-0052 ARC-0059 CNF-0001 WFA-0078; do
  cp "$SRC/command-center/p2-wave/probes/$u/UNIT-ARTIFACT-MANIFEST.json" \
     "$DST/command-center/p2-wave/probes/$u/UNIT-ARTIFACT-MANIFEST.json"
done
export AST_INTEGRATE_ROOT="$DST"
cd "$DST"
for u in ADV-0010 ARC-0052 ARC-0059 CNF-0001 WFA-0078 TST-0187 TST-0224 TST-0225; do
  python3 command-center/p2-wave/_measure_one_delivered.py "$u" 2>&1 | tail -1
done
