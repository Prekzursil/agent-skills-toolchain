#!/usr/bin/env python3
"""Shard-6 wave-4 resume: compact state of the 12 assigned units."""
from __future__ import annotations
import hashlib, json, os, sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
MINE = ["CNF-0149","CNF-0152","CNF-0164","CNF-0167","CNF-0169","CNF-0171",
        "CNF-0172","CNF-0177","CNF-0184","CNF-0188","CNF-0191","CNL-0078"]
NOT_DELIVERING = {"BLOCKED","FAILED","SEVERED","TIMEOUT"}

cat = json.loads(CATALOG.read_text(encoding="utf-8"))
units = {u["id"]: u for u in cat["work_units"]}

def digest(path: Path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()

def man_match(man, art_rel, art_hash):
    rows = man.get("artifacts") or man.get("rows") or []
    if isinstance(man, dict) and not rows:
        # manifest itself may be a list-style row set under another key
        for k in ("files","items","entries"):
            if isinstance(man.get(k), list):
                rows = man[k]; break
    for r in rows:
        if not isinstance(r, dict):
            continue
        rp = str(r.get("path") or r.get("artifact") or "")
        if rp.replace("\\","/").endswith(art_rel.replace("\\","/").split("/")[-1]) or rp.replace("\\","/") == art_rel:
            if r.get("sha256") == art_hash:
                return "MATCH"
            return f"STALE({str(r.get('sha256'))[:12]})"
    return "NO-ROW"

for uid in MINE:
    u = units.get(uid)
    print(f"### {uid}")
    if not u:
        print("  catalog: MISSING"); continue
    out_rel = str(u.get("output_path","")).replace("\\","/")
    sent = u.get("completion_sentinel","")
    gate = u.get("owner_approval_required")
    print(f"  out: {out_rel}")
    print(f"  schema: {u.get('output_schema')}")
    print(f"  sentinel: {sent}  owner_gate: {gate}  deps: {u.get('dependencies')}")
    art = REPO / out_rel
    if art.is_file() and art.stat().st_size > 0:
        try:
            doc = json.loads(art.read_text(encoding="utf-8"))
            st = str(doc.get("state","")).upper()
            print(f"  artifact: EXISTS size={art.stat().st_size} state={st} parses=yes selfblocking={'YES' if st in NOT_DELIVERING else 'no'}")
            rv = doc.get("reviewer") or {}
            if isinstance(rv, dict) and rv:
                print(f"  reviewer: verdict={rv.get('verdict')} independent={rv.get('independent')} by={rv.get('reviewer') or rv.get('by')}")
            else:
                print("  reviewer: none")
        except Exception as e:
            print(f"  artifact: EXISTS size={art.stat().st_size} PARSE-FAIL {type(e).__name__}")
        h = digest(art)
    else:
        print(f"  artifact: ABSENT or EMPTY")
        h = None
    pd = PROBES / uid
    ret_p = pd / "SUBAGENT-RETURN.json"
    man_p = pd / "UNIT-ARTIFACT-MANIFEST.json"
    if ret_p.is_file():
        try:
            ret = json.loads(ret_p.read_text(encoding="utf-8"))
            print(f"  return: status={ret.get('status') or ret.get('state')} named_probes={len(ret.get('named_probes') or ret.get('probes') or [])}")
        except Exception:
            print("  return: UNPARSEABLE")
    else:
        print("  return: ABSENT")
    if man_p.is_file():
        try:
            man = json.loads(man_p.read_text(encoding="utf-8"))
            m = man_match(man, out_rel, h) if h else "NO-ARTIFACT"
            print(f"  manifest: EXISTS -> {m}")
        except Exception:
            print("  manifest: UNPARSEABLE")
    else:
        print("  manifest: ABSENT")
    # receipt dir sidecars
    print()
print("TOTAL catalog units:", len(cat["work_units"]))
