#!/usr/bin/env bash
set -uo pipefail
DST="$HOME/p2-g1"
export AST_INTEGRATE_ROOT="$DST"
cd "$DST"
echo "=== ADV-0010 mirror artifact sha"
python3 - <<'EOF'
import hashlib
from pathlib import Path
p = Path("command-center/adversarial/ADV-0010-gate-code-mutation-survivors.json")
raw = p.read_bytes().replace(b"\r\n", b"\n")
print("mirror", hashlib.sha256(raw).hexdigest(), len(raw))
w = Path("/mnt/c/Users/Prekzursil/source/ast-integrate") / p
raw2 = w.read_bytes().replace(b"\r\n", b"\n")
print("windows", hashlib.sha256(raw2).hexdigest(), len(raw2))
EOF
echo "=== TST-0224"
python3 command-center/p2-wave/_measure_one_delivered.py TST-0224 2>&1 | tail -12
echo "=== TST-0225"
python3 command-center/p2-wave/_measure_one_delivered.py TST-0225 2>&1 | tail -12
