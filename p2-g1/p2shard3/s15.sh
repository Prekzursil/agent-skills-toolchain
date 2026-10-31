#!/bin/bash
cd /home/prekzursil/p2-g1
echo "===try skills repo==="
for f in ".github/workflows/quality.yml" ".github/AUTOMATION.md"; do
  echo "$f -> $(curl -s -o /dev/null -m 20 -w '%{http_code}' https://raw.githubusercontent.com/Prekzursil/skills/main/$f)"
done
echo "===local quality.yml jobs==="
grep -E "^\s{2}[a-z0-9_-]+:|^\s{4}name:" .github/workflows/quality.yml | head -30
echo "===local AUTOMATION.md==="
cat .github/AUTOMATION.md
echo "===BLD-0010 cp1252 detail==="
cd command-center/p2-wave/probes/BLD-0010 && python3 - <<'PYEOF'
import json
import runtime as R
con = R.cp1252_console()
print(json.dumps({k: v for k, v in con.items() if k not in ('mini_list', 'hourglass_planted')}, indent=1, sort_keys=True))
print('mini:', json.dumps(con['mini_list'], indent=1)[:800])
print('hourglass:', json.dumps(con['hourglass_planted'], indent=1)[:500])
PYEOF
