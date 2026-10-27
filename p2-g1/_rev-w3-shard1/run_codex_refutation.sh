#!/usr/bin/env bash
# Independent Codex (openai) refutation pass for units whose catalog
# reviewer_requirement names a Codex/openai refuter or a second vendor.
set -u
REPO="C:/Users/Prekzursil/p2-g1"
OUT="$REPO/_rev-w3-shard1/codex_refutation"
mkdir -p "$OUT"

declare -A P1 P2
P1[ADV-0040]=probe1_delivery_predicate.py;  P2[ADV-0040]=probe2_independent_recheck.py
P1[ADV-0091]=probe1_delivery_predicate.py;  P2[ADV-0091]=probe2_independent_recheck.py
P1[ADV-0096]=probe1_live_gate.py;           P2[ADV-0096]=probe2_semantic_space.py
P1[ADV-0100]=probe1_delivery_predicate.py;  P2[ADV-0100]=probe2_independent_recheck.py
P1[ADV-0109]=probe1_delivery_predicate.py;  P2[ADV-0109]=probe2_independent_recheck.py
P1[ADV-0110]=probe1_delivery_predicate.py;  P2[ADV-0110]=probe2_independent_recheck.py
P1[ADV-0119]=probe1_delivery_predicate.py;  P2[ADV-0119]=probe2_independent_recheck.py
P1[ADV-0123]=probe1_delivery_predicate.py;  P2[ADV-0123]=probe2_independent_recheck.py

UNITS=("$@")
if [ ${#UNITS[@]} -eq 0 ]; then UNITS=(ADV-0040 ADV-0091 ADV-0096 ADV-0100 ADV-0109 ADV-0119 ADV-0123); fi

for UNIT_ID in "${UNITS[@]}"; do
  ART=$(ls "$REPO/command-center/adversarial/${UNIT_ID}-"*.json 2>/dev/null | head -1)
  if [ -z "$ART" ]; then echo "FAILED:artifact-not-found $UNIT_ID"; continue; fi
  ART_REL=${ART#"$REPO/"}
  PROMPT="$OUT/${UNIT_ID}-prompt.txt"
  cat > "$PROMPT" <<EOF
You are an INDEPENDENT cross-vendor refutation reviewer for work-unit $UNIT_ID of the P2 program in this repository (repo root = your working directory).

You did NOT build this unit; a different vendor built it. Your job: re-derive the unit's central finding from the RAW ARTIFACT and the live probes - NOT from any builder report or receipt.

Mandatory steps:
1. Read the raw artifact at $ART_REL and form your own view of its central claim, method, and per-target verdicts BEFORE consulting anything else.
2. Re-run both named probes yourself from the repo root and record their exit codes:
   PYTHONDONTWRITEBYTECODE=1 python command-center/p2-wave/probes/$UNIT_ID/${P1[$UNIT_ID]}
   PYTHONDONTWRITEBYTECODE=1 python command-center/p2-wave/probes/$UNIT_ID/${P2[$UNIT_ID]}
3. Adversarially judge: does the central finding survive YOUR OWN re-derivation? Is any per-target verdict unsupported, any listed control/negative test missing from the artifact, any claim overstated?
4. Do NOT create, modify or delete ANY file. This is a read-only review except the two probe scripts above (program-owned). If a probe fails only due to sandbox write restrictions, record that fact rather than working around it by writing files.

Final message rule: your LAST line must be exactly one JSON object prefixed CODEX-VERDICT, nothing after it:
CODEX-VERDICT {"unit_id":"$UNIT_ID","verdict":"AGREE|REFUTE|PARTIAL","probes_rerun":{"probe1_exit":0,"probe2_exit":0},"finding_rederived":"<one sentence>","objections":"<none, or the precise objection>"}
EOF
  echo "=== $UNIT_ID starting $(date -u +%H:%M:%S)"
  codex exec -C "$REPO" -s workspace-write --skip-git-repo-check - < "$PROMPT" > "$OUT/${UNIT_ID}.log" 2>&1
  echo "=== $UNIT_ID exit=$? $(date -u +%H:%M:%S)"
done
echo ALL-DONE
