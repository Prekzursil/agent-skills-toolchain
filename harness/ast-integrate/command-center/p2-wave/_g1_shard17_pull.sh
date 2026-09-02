#!/usr/bin/env bash
set -euo pipefail
SRC="$HOME/p2-g1"
DST=/mnt/c/Users/Prekzursil/source/ast-integrate
# Copy measured artifacts and per-unit receipts back to Windows (source of truth).
for tree in \
  command-center/adversarial \
  command-center/receipts \
  command-center/audit \
  command-center/research \
  command-center/confirmation \
  command-center/phase3 \
  command-center/phase4 \
  command-center/conformance \
  command-center/foundry \
  command-center/synthesis \
  command-center/wfa \
  command-center/blueprints \
  tools/discovery \
  tools/package_gate \
  tools/artifact_cache \
  tools/council/participants \
  command-center/lib/evidence_snapshot
do
  if [ -e "$SRC/$tree" ]; then
    mkdir -p "$DST/$tree"
    rsync -a --exclude __pycache__ --exclude '*.pyc' "$SRC/$tree/" "$DST/$tree/"
  fi
done
IDS="ADV-0018 ADV-0047 ADV-0076 ADV-0100 ADV-0123 ARC-0016 ARC-0065 ARC-0108 AUD-0033 AUD-0067 BLD-0008 BLD-0039 CC-0014 CNF-0031 CNF-0081 CNF-0127 CNF-0167 CNL-0036 CNL-0095 IMP-0005 IMP-0031 IMP-0053 IMP-0078 IMP-0104 IMP-0124 IMP-0150 IMP-0189 IMP-0217 IMP-0245 IMP-0270 IMP-0296 IMP-0322 IMP-0344 IMP-0367 IMP-0402 IMP-0428 IMP-0464 RES-0004 RES-0058 RES-0125 RES-0161 RES-0191 SYN-0036 TST-0011 TST-0071 TST-0114 TST-0145 TST-0173 TST-0210 TST-0241 TST-0274 TST-0301 TST-0333 WFA-0045 WFA-0094 WFA-0139"
for uid in $IDS; do
  s="$SRC/command-center/p2-wave/probes/$uid"
  d="$DST/command-center/p2-wave/probes/$uid"
  if [ -d "$s" ]; then
    mkdir -p "$d"
    rsync -a --exclude __pycache__ --exclude '*.pyc' \
      --include 'SUBAGENT-RETURN.json' --include 'UNIT-ARTIFACT-MANIFEST.json' \
      --include '*/' --exclude '*' \
      "$s/" "$d/" 2>/dev/null || true
    # also copy json receipts in probe dir
    rsync -a "$s/SUBAGENT-RETURN.json" "$d/SUBAGENT-RETURN.json" 2>/dev/null || true
    rsync -a "$s/UNIT-ARTIFACT-MANIFEST.json" "$d/UNIT-ARTIFACT-MANIFEST.json" 2>/dev/null || true
  fi
done
echo PULL-OK
