#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
rsync -a "$SRC/command-center/p2-wave/seed-stage/" "$DST/command-center/p2-wave/seed-stage/"
rsync -a "$SRC/command-center/p2-wave/_measure_one_delivered.py" "$DST/command-center/p2-wave/_measure_one_delivered.py"
export AST_INTEGRATE_ROOT="$DST"
cd "$DST"
python3 -u "$DST/command-center/p2-wave/seed-stage/_write_fanin.py"
python3 -u "$DST/command-center/p2-wave/seed-stage/fast_fill_receipts.py"
set +e
python3 -u "$DST/command-center/p2-wave/_measure_one_delivered.py" ADV-0005
python3 -u "$DST/command-center/p2-wave/_measure_one_delivered.py" ADV-0010
python3 -u "$DST/command-center/p2-wave/_measure_one_delivered.py" ADV-0003
exit 0
