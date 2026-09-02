#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
copy() { mkdir -p "$DST/$(dirname "$1")"; cp -a "$SRC/$1" "$DST/$1"; echo copied "$1"; }
copy tools/council/phases.py
copy tools/council/antifail/__init__.py
copy tools/council/antifail/unanimity.py
copy tools/foundry/candidate_registry.py
copy tools/workflow_foundry/unknown_probe.py
copy tools/workflow_foundry/blueprint_gate.py
copy hooks/_shared/use_vs_mention.py
copy command-center/schema/contradiction-pairs.schema.json
copy command-center/receipts/BLD-0049.json
copy command-center/p2-wave/probes/CNF-0133/pipeline.py
copy command-center/p2-wave/probes/BLD-0049/UNIT-ARTIFACT-MANIFEST.json
echo COPY-S20-OK
