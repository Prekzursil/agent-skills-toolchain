#!/bin/bash
cd /home/prekzursil/p2-g1
echo "===Prekzursil public repos==="
curl -s -m 20 "https://api.github.com/users/Prekzursil/repos?per_page=100" | python3 -c "import json,sys; d=json.load(sys.stdin); print([r['name'] for r in d] if isinstance(d,list) else d)"
echo "===local workflows full==="
ls .github/workflows/
echo "===AUTOMATION.md seven==="
grep -in "required_status_checks" .github/AUTOMATION.md | head -5
echo "===unit_manifest usage==="
python3 tools/command-center/unit_manifest.py --help 2>&1 | head -30
