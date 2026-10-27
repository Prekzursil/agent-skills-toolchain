#!/usr/bin/env python3
"""Receipt-aware fleet census (read-only). Static-delivered predicate from
_measure_one_delivered.py + receipt state / reviewer closure count."""
import hashlib, json
from collections import Counter
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

cat = json.loads(CATALOG.read_text(encoding="utf-8"))
units = cat["work_units"]

def digest_file(p: Path):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

cnt = Counter()
closed, awaiting, problems = [], [], {}
for u in units:
    uid = u.get("id")
    out_rel = str(u.get("output_path") or "").replace("\\", "/")
    art = REPO / out_rel if out_rel else None
    def prob(k):
        cnt[k] += 1
        problems.setdefault(k, []).append(uid)
    if not out_rel or not art.is_file() or art.stat().st_size <= 0:
        prob("predicate:absent"); continue
    try:
        text = art.read_text(encoding="utf-8"); doc = json.loads(text)
    except Exception:
        prob("unparseable"); continue
    if not isinstance(doc, dict):
        prob("non-dict"); continue
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        prob(f"self-{st}"); continue
    sentinel = str(u.get("completion_sentinel") or "")
    if sentinel and sentinel not in text:
        prob("sentinel-absent"); continue
    pd = PROBES / uid
    ret_p, man_p = pd / "SUBAGENT-RETURN.json", pd / "UNIT-ARTIFACT-MANIFEST.json"
    if not ret_p.is_file() or not man_p.is_file():
        prob("probe-files-absent"); continue
    try:
        ret = json.loads(ret_p.read_text(encoding="utf-8"))
        rst = str(ret.get("status") or ret.get("state") or "").upper()
    except Exception:
        rst = "UNPARSEABLE"
    if rst in NOT_DELIVERING or rst == "UNPARSEABLE":
        prob(f"return:{rst}"); continue
    try:
        man = json.loads(man_p.read_text(encoding="utf-8"))
    except Exception:
        prob("manifest-unparseable"); continue
    rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict) and a.get("unit_id") == uid]
    if not rows:
        prob("manifest-row-absent"); continue
    live_sha = digest_file(art)
    if not any(str(a.get("path") or "").replace("\\","/") == out_rel and str(a.get("sha256") or "") == live_sha and a.get("present") is True for a in rows):
        prob("manifest-sha-mismatch"); continue
    # receipt-aware closure check: receipt = receipts/<id>.json OR artifact itself
    clo = False
    rp = REPO / "command-center" / "receipts" / f"{uid}.json"
    for src in (rp, art):
        if src.is_file():
            try:
                r = json.loads(src.read_text(encoding="utf-8"))
                rv = r.get("reviewer") if isinstance(r, dict) else None
                if isinstance(rv, dict) and rv.get("verdict") == "PASS" and rv.get("independent") is True:
                    clo = True; break
            except Exception:
                pass
    if clo:
        cnt["CLOSED(static-green+receipt-or-artifact PASS independent)"] += 1
        closed.append(uid)
    else:
        cnt["AWAITING-REVIEW(static-green, no PASS-independent closure)"] += 1
        awaiting.append(uid)

print("catalog:", len(units))
for k, v in cnt.most_common():
    print(f"  {k}: {v}")
for k, v in sorted(problems.items(), key=lambda kv: -len(kv[1])):
    print(f"  PROBLEM {k}: {len(v)} e.g. {v[:8]}")
my = {"RES-0168","RES-0175","RES-0176","RES-0179","RES-0180","RES-0182","TST-0018","TST-0028","TST-0032","TST-0057","TST-0060","TST-0066"}
cs, as_ = set(closed), set(awaiting)
print("my12 closed:", len(my & cs), "awaiting:", len(my & as_), "missing:", sorted(my - cs - as_))
print("awaiting list:", awaiting)
