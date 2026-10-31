#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
files='
command-center/p2-wave/seed-stage/g1_python.py
command-center/p2-wave/seed-stage/_g1_env_remeasure8.sh
tools/plugin/packet.py
tools/plugin/permission_diff.py
tools/plugin/classifier.py
tools/plugin/gate.py
tools/plugin/independent_differ.py
tools/plugin/repair.py
tools/plugin/drift.py
tools/plugin/tests/test_divergence_packet.py
tools/plugin/tests/test_repair_respects_divergence.py
plugin/packet.py
command-center/p2-wave/seed-stage/p2_jsonschema_hook.py
command-center/p2-wave/probes/AUD-0074/probe2_timestamp_order.py
command-center/p2-wave/probes/AUD-0074/corpus.py
command-center/p2-wave/probes/ARC-0049/probe2_rollback.py
command-center/p2-wave/probes/RES-0177/live.py
command-center/p2-wave/probes/WFA-0045/probe2_both_states.py
command-center/p2-wave/probes/ADV-0139/attribution.py
command-center/p2-wave/probes/WFA-0039/extract.py
command-center/research/RES-0102.json
command-center/research/teardown/RES-0177-teardown-installed-local-plugins.json
command-center/wfa/WFA-0044-workflow-ir-spec.json
command-center/p2-wave/probes/RES-0177/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/RES-0102/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/WFA-0044/UNIT-ARTIFACT-MANIFEST.json
'
for f in $files; do
  mkdir -p "$DST/$(dirname "$f")"
  rsync -a "$SRC/$f" "$DST/$f"
done
# probe trees that gained fixtures / path retargets
rsync -a "$SRC/command-center/p2-wave/probes/ARC-0049/" "$DST/command-center/p2-wave/probes/ARC-0049/"
rsync -a "$SRC/command-center/p2-wave/probes/IMP-0025/" "$DST/command-center/p2-wave/probes/IMP-0025/"
rsync -a "$SRC/command-center/p2-wave/probes/IMP-0036/" "$DST/command-center/p2-wave/probes/IMP-0036/"
rsync -a "$SRC/command-center/p2-wave/probes/RES-0177/" "$DST/command-center/p2-wave/probes/RES-0177/"
echo DELTA-RSYNC-OK
