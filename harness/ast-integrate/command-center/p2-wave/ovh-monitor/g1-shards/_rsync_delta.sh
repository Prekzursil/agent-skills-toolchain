#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
files='
command-center/schema/audit-inventory.schema.json
command-center/p2-wave/probes/AUD-0024/probe1_declared_metadata.py
command-center/p2-wave/probes/AUD-0024/schema_local.py
command-center/p2-wave/probes/CNF-0183/isolate.py
tools/plugin/exit_codes.py
plugin/__init__.py
marketplace/__init__.py
workflow_foundry/__init__.py
tools/plugin/__init__.py
tools/plugin/doctor/coverage.py
tools/plugin/scenario.py
tools/marketplace/independent_sweep.py
tools/marketplace/name_grammar.py
tools/marketplace/__init__.py
tools/workflow_foundry/license_extract.py
tools/glob-argv-guard/fixtures/concatenated_spawn.py
command-center/receipts/CNF-0183.json
command-center/p2-wave/probes/CNF-0183/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/CNF-0183/emit_receipt.py
'
for f in $files; do
  mkdir -p "$DST/$(dirname "$f")"
  rsync -a "$SRC/$f" "$DST/$f"
done
echo DELTA-RSYNC-OK
