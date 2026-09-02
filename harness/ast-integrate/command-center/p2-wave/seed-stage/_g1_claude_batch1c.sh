#!/usr/bin/env bash
set -uo pipefail
DST="$HOME/p2-g1"
export AST_INTEGRATE_ROOT="$DST"
cd "$DST"
sha() { python3 -c "import hashlib,sys;raw=open(sys.argv[1],'rb').read().replace(b'\r\n',b'\n');print(hashlib.sha256(raw).hexdigest(),len(raw))" "$1"; }
A=command-center/adversarial/ADV-0010-gate-code-mutation-survivors.json
echo before; sha "$A"
python3 command-center/p2-wave/_measure_one_delivered.py ADV-0010 >/dev/null 2>&1
echo after1; sha "$A"
python3 command-center/p2-wave/_measure_one_delivered.py ADV-0010 >/dev/null 2>&1
echo after2; sha "$A"
