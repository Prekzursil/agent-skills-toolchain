#!/usr/bin/env python3
"""Independent reviewer fast checks for shard-18 wave-2 (12 units).
No probe execution here - probes run separately via _measure_one_delivered.py."""
import hashlib, json, sys
from pathlib import Path
WS = Path("C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(WS / "command-center/p2-wave"))
import _p2lib as P
CAT = json.load(open(WS / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
BYID = {u["id"]: u for u in CAT["work_units"]}
UNITS = ["RES-0112","RES-0114","RES-0128","RES-0131","RES-0132","RES-0137",
         "RES-0140","RES-0141","RES-0144","RES-0148","RES-0149","RES-0150"]
BAD = {"BLOCKED","FAILED","SEVERED","TIMEOUT"}
for uid in UNITS:
    problems = []
    e = BYID[uid]
    out = WS.joinpath(*e["output_path"].split("/"))
    if not out.is_file():
        problems.append("artifact-missing")
    else:
        raw = out.read_bytes()
        if len(raw) == 0: problems.append("artifact-empty")
        try:
            doc = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            problems.append(f"unparseable:{type(exc).__name__}")
            doc = None
        if isinstance(doc, dict):
            st = str(doc.get("state") or "").upper()
            if st in BAD: problems.append(f"self-declared:{st}")
        # schema validation
        errs = P.validate(doc, e["output_schema"])
        if errs: problems.append("schema:" + "; ".join(map(str, errs[:3])))
        # receipt
        rp = WS / "command-center/receipts" / f"{uid}.json"
        try:
            rec = json.loads(rp.read_text(encoding="utf-8"))
        except Exception as exc:
            problems.append(f"receipt-unparseable:{type(exc).__name__}")
            rec = None
        if rec:
            if rec.get("state") not in ("BLOCKED", "SUCCESS", "FAILED"):
                problems.append(f"receipt-state:{rec.get('state')}")
            if rec.get("failure", {}).get("classification") != ["reviewer-absent"] and rec.get("state") == "BLOCKED":
                problems.append(f"receipt-class:{rec.get('failure',{}).get('classification')}")
        # manifest sha (CRLF-normalized)
        mp = WS / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        try:
            man = json.loads(mp.read_text(encoding="utf-8"))
        except Exception as exc:
            problems.append(f"manifest-unparseable:{type(exc).__name__}")
            man = None
        if man and out.is_file():
            nsha = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
            rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == uid and a.get("role") == "primary"]
            hit = [a for a in rows if a.get("path","").replace("\\","/") == e["output_path"] and a.get("sha256") == nsha and a.get("present") is True]
            if not hit: problems.append(f"manifest-sha-mismatch live={nsha[:12]} rows={[(a.get('sha256','')[:12], a.get('present')) for a in rows]}")
    print(("PASS " if not problems else "FAIL ") + uid + (" " + " | ".join(problems) if problems else ""))
