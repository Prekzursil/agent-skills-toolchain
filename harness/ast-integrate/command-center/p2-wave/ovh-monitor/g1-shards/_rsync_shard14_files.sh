#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
copy() {
  mkdir -p "$DST/$(dirname "$1")"
  rsync -a "$SRC/$1" "$DST/$1"
}
bash /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_rsync_shard14.sh
copy command-center/p2-wave/seed-stage/g1_python.py
copy tools/council/participants/select_expertise.py
copy tools/council/protocol/scenario.py
copy tools/sync/classifier.py
copy tools/router/hook_contract.py
copy tools/command-center/fanout_cost_model.py
copy command-center/receipts/IMP-0364.json
copy command-center/receipts/TST-0172.json
copy command-center/receipts/TST-0029.json
copy command-center/receipts/IMP-0397.json
copy command-center/p2-wave/probes/IMP-0364/UNIT-ARTIFACT-MANIFEST.json
copy command-center/p2-wave/probes/TST-0172/UNIT-ARTIFACT-MANIFEST.json
copy command-center/p2-wave/probes/TST-0029/UNIT-ARTIFACT-MANIFEST.json
copy command-center/p2-wave/probes/IMP-0397/UNIT-ARTIFACT-MANIFEST.json
copy command-center/p2-wave/probes/IMP-0243/probe1_planted_credential.py
copy command-center/p2-wave/probes/IMP-0243/probe2_rotation_ast.py
copy tools/council/stability.py
copy tools/command-center/fanout_cost_model.py
copy command-center/receipts/TST-0172.json
copy command-center/receipts/TST-0029.json
copy command-center/p2-wave/probes/TST-0172/UNIT-ARTIFACT-MANIFEST.json
copy command-center/p2-wave/probes/TST-0029/UNIT-ARTIFACT-MANIFEST.json
mkdir -p "$DST/hooks/_dispatch"
rsync -a "$SRC/hooks/_dispatch/" "$DST/hooks/_dispatch/"
rsync -a "$SRC/command-center/foundry/revocation/" "$DST/command-center/foundry/revocation/"
echo FILES-OK
