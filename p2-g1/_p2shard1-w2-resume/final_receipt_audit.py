import json
from pathlib import Path
mine = ["ADV-0037","ADV-0038","ADV-0040","ADV-0090","ADV-0091","ADV-0096","ADV-0100","ADV-0109","ADV-0110","ADV-0117","ADV-0119","ADV-0123"]
ok = True
for uid in mine:
    rc = json.loads((Path("command-center/receipts")/f"{uid}.json").read_text(encoding="utf-8"))
    state = str(rc.get("state","")).upper()
    f = rc.get("failure") or {}
    cls = f.get("classification") or []
    rev = rc.get("reviewer") or {}
    bad = []
    if state == "SUCCESS": bad.append("state=SUCCESS (builder cannot close)")
    if state not in ("SUCCESS","BLOCKED"): bad.append(f"state={state}")
    if "reviewer-absent" not in cls: bad.append(f"classification={cls}")
    if rev.get("verdict") == "PASS" and rev.get("independent"): bad.append("has independent closure (should have kept, verify live)")
    tag = "OK " if not bad else "!! "
    if bad: ok = False
    print(f"{tag}{uid} state={state} class={cls} reviewer={rev.get('verdict','-')}/{rev.get('independent','-')}" + (" <- " + "; ".join(bad) if bad else ""))
r38 = json.loads((Path("command-center/receipts")/"ADV-0038.json").read_text(encoding="utf-8"))
print("ADV-0038 notes tail:", r38.get("notes","")[-230:])
print("ADV-0038 receipt artifact row bytes:", [a.get("bytes") for a in r38.get("artifacts",[])])
print("ALL-RECEIPTS:", "GREEN" if ok else "ISSUES")
