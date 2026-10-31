import hashlib
import json
import subprocess
import sys
from pathlib import Path

home = Path.home()
REPO = home / "p2-g1"
my = ["IMP-0194", "IMP-0195", "IMP-0198", "IMP-0202", "IMP-0204", "IMP-0207",
      "IMP-0219", "IMP-0223", "IMP-0224", "IMP-0228", "IMP-0229", "IMP-0261"]

def digest(p):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()

print("unit      | receipt_state | reviewer            | probes | manifest_sha_match")
for uid in my:
    rec_p = REPO / "command-center/receipts" / f"{uid}.json"
    pd = REPO / "command-center/p2-wave/probes" / uid
    rec = json.loads(rec_p.read_text(encoding="utf-8"))
    rv = rec.get("reviewer") or {}
    rvtxt = "-"
    if rv:
        rvtxt = f"{rv.get('verdict')}/ind={rv.get('independent')}"
    ret = json.loads((pd / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
    probes_ok = all(np.get("exit_code") == 0 for np in ret.get("named_probes") or [])
    man = json.loads((pd / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
    live = digest(rec_p)
    match = any(a.get("unit_id") == uid
                and str(a.get("path")).replace("\\", "/") == f"command-center/receipts/{uid}.json"
                and a.get("sha256") == live and a.get("present") is True
                for a in man.get("artifacts") or [])
    st = rec.get("state")
    if st == "BLOCKED":
        ok = probes_ok and match and bool(rec.get("failure", {}).get("classification"))
    else:
        ok = probes_ok and match
    print(f"{uid} | {st:<13} | {rvtxt:<19} | {'exit0' if probes_ok else 'FAIL'}     | "
          f"{'MATCH' if match else 'MISMATCH'} {'-> OK' if ok else '-> BROKEN'}")
