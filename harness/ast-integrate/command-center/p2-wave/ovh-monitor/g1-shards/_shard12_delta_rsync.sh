#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST=/home/prekzursil/p2-g1
mkdir -p "$DST"
files='
tools/plugin/trees.py
tools/plugin/rollback.py
tools/plugin/migration.py
tools/plugin/__init__.py
tools/plugin/tests/test_migration_framework.py
tools/council/context.py
tools/council/vote/ballots.py
tools/council/integrity/recusal.py
tools/council/integrity/__init__.py
tools/council/artifacts/store.py
tools/marketplace/index_migrate.py
tools/marketplace/manifest_reader.py
tools/marketplace/tests/test_index_migrate.py
platform/lib/foundry/capability/taxonomy.py
platform/lib/foundry/capability/vectorize.py
platform/lib/foundry/capability/__init__.py
command-center/foundry/__init__.py
command-center/receipt_writer.py
command-center/id-namespace-allocation.json
command-center/receipts/IMP-0047.json
command-center/receipts/IMP-0361.json
command-center/receipts/BLD-0040.json
command-center/confirmation/CNF-0025-repro-specificity.json
command-center/confirmation/CNF-0098-macos-reachability.json
command-center/phase3/A9/COST.json
command-center/phase3/BLIND-BUNDLE/INDEX.json
command-center/phase4/conformance/ARC-0098.json
command-center/audit/AUD-0095-freeze-inventory.json
command-center/p2-wave/probes/AUD-0061/census.py
command-center/p2-wave/probes/CNF-0098/estate.py
command-center/p2-wave/probes/ARC-0098/runner.py
command-center/p2-wave/probes/IMP-0047/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/IMP-0361/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/BLD-0040/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/CNF-0025/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/CNF-0098/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/ARC-0060/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/ARC-0067/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/ARC-0098/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/AUD-0095/UNIT-ARTIFACT-MANIFEST.json
plugin/__init__.py
'
# LF-only copy
export MSYS_NO_PATHCONV=1
n=0
for f in $files; do
  if [ -f "$SRC/$f" ]; then
    mkdir -p "$DST/$(dirname "$f")"
    cp -a "$SRC/$f" "$DST/$f"
    n=$((n+1))
  fi
done
# remove shadowing stubs if still present in DST
rm -f "$DST/plugin/migration.py" "$DST/plugin/rollback.py" "$DST/council/context.py"
echo DELTA-COPY-OK n=$n
