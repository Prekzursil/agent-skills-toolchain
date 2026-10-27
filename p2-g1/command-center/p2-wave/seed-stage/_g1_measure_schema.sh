#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="${HOME}/p2-g1"
cd "${AST_INTEGRATE_ROOT}"
for uid in ARC-0050 AUD-0059 BLD-0034 CC-0019 CNF-0072 CNL-0020 CNL-0099 WFA-0148; do
  echo "==== ${uid} ===="
  python3 command-center/p2-wave/_measure_one_delivered.py "${uid}"
  echo "EXIT:${uid}:$?"
done
