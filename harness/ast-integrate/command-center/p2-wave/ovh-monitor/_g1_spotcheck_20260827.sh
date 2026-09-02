#!/bin/bash
cd /home/prekzursil/p2-g1
export AST_INTEGRATE_ROOT=/home/prekzursil/p2-g1
python3 - <<'EOF'
import json
rows = [json.loads(l) for l in open('/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-local-full.jsonl')]
oks = [r['id'] for r in rows if r['ok']]
print('OK-NONADV-SAMPLE:', [i for i in oks if not i.startswith('ADV')][:4])
EOF
for id in ADV-0001 ADV-0002 ARC-0001; do
  echo "== $id"
  python3 command-center/p2-wave/_measure_one_delivered.py "$id" 2>&1 | tail -1
done
echo SPOT-PART1-DONE
