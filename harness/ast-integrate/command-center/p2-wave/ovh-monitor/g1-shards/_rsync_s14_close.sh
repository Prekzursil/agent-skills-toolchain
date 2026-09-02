#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
copy() { mkdir -p "$DST/$(dirname "$1")"; rsync -a "$SRC/$1" "$DST/$1"; }
copy platform/blueprints/security/callset.py
copy command-center/p2-wave/probes/IMP-0243/probe1_planted_credential.py
copy command-center/p2-wave/probes/IMP-0243/probe2_rotation_ast.py
copy command-center/p2-wave/probes/IMP-0269/select_expertise.py
copy command-center/p2-wave/probes/IMP-0269/scenario.py
copy command-center/p2-wave/probes/CNL-0087/schema_local.py
copy command-center/p2-wave/probes/CNF-0028/schema_check.py
copy command-center/p2-wave/probes/RES-0053/schema_local.py
copy command-center/adversarial/ADV-0075-filename-path-unicode-injection.json
copy command-center/phase3/A9/MIGRATION.json
copy command-center/receipts/TST-0029.json
copy command-center/p2-wave/probes/TST-0029/UNIT-ARTIFACT-MANIFEST.json
copy command-center/p2-wave/probes/ADV-0075/UNIT-ARTIFACT-MANIFEST.json
copy command-center/p2-wave/probes/ARC-0063/UNIT-ARTIFACT-MANIFEST.json
copy command-center/p2-wave/probes/ARC-0063/probe1_stage_gates.py
copy command-center/p2-wave/probes/ARC-0063/probe2_rollback.py
copy command-center/receipts/CNF-0162.json
copy command-center/receipts/IMP-0317.json
copy command-center/receipts/TST-0206.json
copy command-center/receipts/TST-0200.json
copy command-center/p2-wave/probes/CNF-0162/UNIT-ARTIFACT-MANIFEST.json
copy command-center/p2-wave/probes/IMP-0317/UNIT-ARTIFACT-MANIFEST.json
copy command-center/p2-wave/probes/TST-0206/UNIT-ARTIFACT-MANIFEST.json
copy command-center/p2-wave/probes/TST-0200/UNIT-ARTIFACT-MANIFEST.json
rm -f "$DST/tools/council/participants/select_expertise.py"
echo CLOSE-RSYNC-OK
