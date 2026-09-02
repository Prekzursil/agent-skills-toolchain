#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
rm -f "$DST/tools/workflow.py" "$DST/tools/synthesis.py"
for rel in \
  tools/council \
  tools/workflow \
  tools/synthesis \
  tools/detector_control \
  tools/agentspec/agentspec \
  tools/plugin \
  tools/marketplace \
  tools/router \
  tools/lib \
  tools/command-center \
  command-center/adapters \
  platform/schema \
  command-center/schema
do
  mkdir -p "$DST/$rel"
  rsync -a "$SRC/$rel/" "$DST/$rel/"
  echo synced "$rel"
done
rsync -a "$SRC/command-center/receipt_validate.py" "$DST/command-center/receipt_validate.py"
rsync -a "$SRC/command-center/wfa/" "$DST/command-center/wfa/"
rsync -a "$SRC/command-center/adversarial/" "$DST/command-center/adversarial/"
for uid in ADV-0013 ADV-0065 IMP-0116 CNF-0151 TST-0315 WFA-0010 IMP-0017 IMP-0065 IMP-0090 IMP-0137 IMP-0162 IMP-0205 IMP-0229 IMP-0260 IMP-0287 IMP-0310 IMP-0332 IMP-0355 IMP-0390 IMP-0421 IMP-0453 SYN-0019 TST-0014 TST-0226 TST-0260 TST-0289 AUD-0007 CNF-0012 CNF-0065 CNF-0066 SYN-0005
do
  if [ -d "$SRC/command-center/p2-wave/probes/$uid" ]; then
    mkdir -p "$DST/command-center/p2-wave/probes/$uid"
    rsync -a "$SRC/command-center/p2-wave/probes/$uid/" "$DST/command-center/p2-wave/probes/$uid/"
  fi
done
python3 - <<'PY'
from pathlib import Path
import re
root = Path.home() / "p2-g1"
old = re.compile(r"file:///C:/Users/Prekzursil/source/ast-integrate/")
new = "https://ast-integrate.invalid/"
n = 0
for d in (root / "platform" / "schema", root / "command-center" / "schema"):
    if not d.is_dir():
        continue
    for p in d.rglob("*.json"):
        text = p.read_text(encoding="utf-8")
        nxt = old.sub(new, text)
        nxt = re.sub(r"file://[^\"\\\s]+?(?=/(?:platform|command-center)/schema/)", new.rstrip("/"), nxt)
        if nxt != text:
            p.write_text(nxt, encoding="utf-8")
            n += 1
print("schema-rebased", n)
print("wf.py", (root / "tools" / "workflow.py").exists())
p = root / "platform" / "schema" / "artifact-class-profiles.schema.json"
print("id", p.read_text(encoding="utf-8").splitlines()[2][:110])
print("mcp", (root / "tools" / "plugin" / "mcp_activation.py").stat().st_size)
PY
echo TARGETED-RSYNC-OK
