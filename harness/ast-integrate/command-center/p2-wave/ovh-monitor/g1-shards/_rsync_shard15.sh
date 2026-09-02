#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
files='
tools/shell/pathconv.py
tools/shell/__init__.py
tools/wfa/__init__.py
tools/wfa/nondeterminism.py
tools/plugin/pack.py
tools/plugin/payload_allowlist.py
tools/plugin/fixture_repo.py
tools/plugin/unique_line_differ.py
tools/plugin/message_renderer.py
tools/plugin/redaction.py
tools/plugin/update.py
tools/plugin/tests/test_pack_determinism.py
tools/plugin/tests/test_pack_uses_blob_bytes.py
tools/marketplace/integrity_sweep.py
tools/marketplace/deprecation.py
tools/marketplace/warning_channel.py
tools/router/inject.py
tools/agentspec/agentspec/checkpoint.py
tools/workflow_forge/best_of_breed.py
command-center/blueprints/__init__.py
command-center/blueprints/policy_as_code.py
command-center/blueprints/legal_compliance.py
command-center/blueprints/registry.py
command-center/blueprints/ci_evaluate.py
command-center/blueprints/privacy.py
command-center/blueprints/governance_proposal.py
command-center/blueprints/contract.py
command-center/foundry/capability_diff.py
command-center/foundry/__init__.py
platform/lib/foundry/capability_diff.py
command-center/schema/source-lineage.schema.json
command-center/schema/evidence-tier.schema.json
command-center/schema/confidence-band.schema.json
command-center/schema/settling-probe.schema.json
command-center/schema/claim-edge.schema.json
command-center/schema/freshness-stamp.schema.json
command-center/schema/snapshot-sha256.schema.json
command-center/p2-wave/probes/CNF-0128/schema_val.py
command-center/p2-wave/probes/CNL-0089/local_schema.py
command-center/p2-wave/probes/SYN-0020/schema_local.py
command-center/p2-wave/probes/SYN-0041/generate.py
command-center/p2-wave/probes/TST-0110/schema_local.py
command-center/p2-wave/probes/IMP-0398/schema_util.py
command-center/foundry/WFA-0140-capability-loss-detector-for-fusion.json
command-center/p2-wave/probes/WFA-0140/UNIT-ARTIFACT-MANIFEST.json
'
for f in $files; do
  mkdir -p "$DST/$(dirname "$f")"
  rsync -a "$SRC/$f" "$DST/$f"
done
rm -f "$DST/tools/wfa.py"
echo DELTA-RSYNC-OK
ls -l "$DST/tools/wfa/nondeterminism.py" "$DST/tools/shell/pathconv.py" "$DST/command-center/blueprints/policy_as_code.py"
