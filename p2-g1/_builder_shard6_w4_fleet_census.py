#!/usr/bin/env python3
"""Fleet census v2 — exact canonical manifest-row logic from _measure_one_delivered.py."""
from __future__ import annotations
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
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()

cnt = Counter()
green_full, green_norev, no_rev_detail = [], [], []
problems = {}
for u in units:
    uid = u.get("id")
    out_rel = str(u.get("output_path") or "").replace("\\", "/")
    art = REPO / out_rel if out_rel else None
    if not out_rel or not art.is_file() or art.stat().st_size <= 0:
        cnt["predicate:absent"] += 1
        problems.setdefault("predicate:absent", []).append(uid)
        continue
    try:
        text = art.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception:
        cnt["unparseable"] += 1
        problems.setdefault("unparseable", []).append(uid)
        continue
    if not isinstance(doc, dict):
        cnt["non-dict"] += 1
        problems.setdefault("non-dict", []).append(uid)
        continue
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        cnt[f"self-{st}"] += 1
        problems.setdefault(f"self-{st}", []).append(uid)
        continue
    sentinel = str(u.get("completion_sentinel") or "")
    if sentinel and sentinel not in text:
        cnt["sentinel-absent"] += 1
        problems.setdefault("sentinel-absent", []).append(uid)
        continue
    pd = PROBES / uid
    ret_p, man_p = pd / "SUBAGENT-RETURN.json", pd / "UNIT-ARTIFACT-MANIFEST.json"
    if not ret_p.is_file() or not man_p.is_file():
        cnt["probe-files-absent"] += 1
        problems.setdefault("probe-files-absent", []).append(uid)
        continue
    try:
        ret = json.loads(ret_p.read_text(encoding="utf-8"))
        rst = str(ret.get("status") or ret.get("state") or "").upper()
    except Exception:
        rst = "UNPARSEABLE"
    if rst in NOT_DELIVERING or rst == "UNPARSEABLE":
        cnt[f"return:{rst}"] += 1
        problems.setdefault(f"return:{rst}", []).append(uid)
        continue
    try:
        man = json.loads(man_p.read_text(encoding="utf-8"))
    except Exception:
        cnt["manifest-unparseable"] += 1
        problems.setdefault("manifest-unparseable", []).append(uid)
        continue
    rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict) and a.get("unit_id") == uid]
    if not rows:
        cnt["manifest-row-absent"] += 1
        problems.setdefault("manifest-row-absent", []).append(uid)
        continue
    live_sha = digest_file(art)
    matching = [a for a in rows
                if str(a.get("path") or "").replace("\\", "/") == out_rel
                and str(a.get("sha256") or "") == live_sha
                and a.get("present") is True]
    if not matching:
        cnt["manifest-sha-mismatch"] += 1
        problems.setdefault("manifest-sha-mismatch", []).append(uid)
        continue
    rv = doc.get("reviewer") or {}
    has_rev = isinstance(rv, dict) and rv.get("verdict") == "PASS" and rv.get("independent") is True
    if has_rev:
        cnt["static-green+reviewer"] += 1
        green_full.append(uid)
    else:
        cnt["static-green-no-reviewer"] += 1
        green_norev.append(uid)
        no_rev_detail.append(uid)

print("catalog:", len(units))
for k, v in cnt.most_common():
    print(f"  {k}: {v}")
print("STATIC-GREEN total:", cnt["static-green+reviewer"] + cnt["static-green-no-reviewer"])
print("  with reviewer PASS closure:", len(green_full))
print("  without:", len(green_norev), no_rev_detail[:20])
for k, v in sorted(problems.items(), key=lambda kv: -len(kv[1])):
    print(f"  PROBLEM {k}: {len(v)} e.g. {v[:6]}")
mine = {"CNF-0149","CNF-0152","CNF-0164","CNF-0167","CNF-0169","CNF-0171","CNF-0172","CNF-0177","CNF-0184","CNF-0188","CNF-0191","CNL-0078"}
gs = set(green_full) | set(green_norev)
print("my shard all static-green:", mine <= gs)
