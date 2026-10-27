#!/usr/bin/env bash
set -euo pipefail
SRC="$HOME/p2-g1"
DST=/mnt/c/Users/Prekzursil/source/ast-integrate
files='
command-center/adversarial/ADV-0114-final-findings-mechanism-collapse.json
command-center/p2-wave/probes/ADV-0114/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/ADV-0114/SUBAGENT-RETURN.json
command-center/wfa/WFA-0005-classification-vocabulary-audit.json
command-center/p2-wave/probes/WFA-0005/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/WFA-0005/SUBAGENT-RETURN.json
command-center/wfa/WFA-0069-adopt-as-is-executable-test.json
command-center/p2-wave/probes/WFA-0069/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/WFA-0069/SUBAGENT-RETURN.json
command-center/wfa/WFA-0114-headtohead-scoring-rubric.json
command-center/p2-wave/probes/WFA-0114/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/WFA-0114/SUBAGENT-RETURN.json
command-center/audit/AUD-0085-encoding-bom-mojibake-census.json
command-center/p2-wave/probes/AUD-0085/UNIT-ARTIFACT-MANIFEST.json
command-center/p2-wave/probes/AUD-0085/SUBAGENT-RETURN.json
'
for f in $files; do
  if [[ -f "$SRC/$f" ]]; then
    mkdir -p "$DST/$(dirname "$f")"
    rsync -a --checksum "$SRC/$f" "$DST/$f"
    echo PULL "$f"
  else
    echo MISSING "$f"
  fi
done
echo PULL-OK
