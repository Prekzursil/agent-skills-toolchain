#!/bin/bash
cd /home/prekzursil/p2-g1
echo "===A: AUD-0044 connectivity==="
for u in "https://raw.githubusercontent.com/Prekzursil/agent-skills-toolchain/main/.github/workflows/quality.yml" "https://raw.githubusercontent.com/Prekzursil/agent-skills-toolchain/main/.github/AUTOMATION.md" "https://api.github.com/rate_limit" "https://api.github.com/repos/Prekzursil/agent-skills-toolchain" "https://github.com/Prekzursil/agent-skills-toolchain"; do
  echo "URL $u -> $(curl -s -o /dev/null -m 20 -w '%{http_code}' -A 'AUD-0044-probe' "$u")"
done
echo "===B: BLD-0044 unshare test==="
unshare -n true 2>&1; echo "unshare rc=$?"
cat /proc/sys/kernel/unprivileged_userns_clone 2>/dev/null || echo "no unprivileged_userns_clone sysctl"
cat /proc/sys/user/max_user_namespaces 2>/dev/null
cat /proc/sys/apparmor_restrict_unprivileged_userns 2>/dev/null || echo "no apparmor sysctl"
id
echo "===F: BLD-0057 schema errors==="
python3 - <<'PYEOF'
import json, jsonschema
from pathlib import Path
REPO = Path('/home/prekzursil/p2-g1')
doc = json.loads((REPO/'command-center/receipts/BLD-0057.json').read_text())
schema = json.loads((REPO/'command-center/schema/scale-model.schema.json').read_text())
for e in jsonschema.Draft7Validator(schema).iter_errors(doc):
    print('ERR path=%s msg=%s' % ('/'.join(str(x) for x in e.absolute_path), e.message))
PYEOF
