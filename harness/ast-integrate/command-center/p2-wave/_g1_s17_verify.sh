#!/usr/bin/env bash
set -euo pipefail
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$AST_INTEGRATE_ROOT"
export SHARD17_MEASURE_LOG="$HOME/p2-g1-shard17-verify.jsonl"
python3 -B command-center/p2-wave/_g1_shard17_measure_all.py \
  ADV-0018 ADV-0047 ADV-0076 AUD-0033 CC-0014 \
  IMP-0005 IMP-0150 IMP-0245 IMP-0270 IMP-0464 \
  RES-0004 TST-0173 WFA-0045
echo VERIFY-DONE
