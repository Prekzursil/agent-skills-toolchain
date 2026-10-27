#!/usr/bin/env python3
"""Fleet census for the estate P2 program: staged green funnel over all 2007 units.

Stage A artifact predicate (exists/non-empty/parses/not-self-blocked/sentinel)
Stage B manifest primary-row sha256 match (CRLF->LF)
Stage C output_schema clean (canonical schema_resolver)
Stage D receipt admission ACCEPT (command-center/receipt_validate.admit_doc)
Stage E genuine independent reviewer closure (PASS + independent + not stamped)

full green = A and B and C and D and E. Emits census_out.json + prints funnel.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
sys.path.insert(0, str(REPO / "command-center"))
import schema_resolver  # noqa: E402
import receipt_validate  # noqa: E402

NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def lf_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = {u["id"]: u for u in cat["work_units"] if isinstance(u.get("id"), str)}
ids = sorted(units)
ids_set = set(ids)

stage = Counter()
state_dist = Counter()
detail = {}
gate_reason = Counter()

admission_cache = {}


def admit(doc):
    key = id(doc)
    if key not in admission_cache:
        try:
            admission_cache[key] = receipt_validate.admit_doc(doc, REPO)[0]
        except Exception as exc:
            admission_cache[key] = "ERROR:" + type(exc).__name__
    return admission_cache[key]


for uid in ids:
    e = units[uid]
    out_rel = str(e.get("output_path", "")).replace("\\", "/")
    schemas = [x.strip() for x in str(e.get("output_schema") or "").split("+") if x.strip()]
    art = REPO / out_rel if out_rel else None
    d = {}

    # A
    doc = None
    if not out_rel or not art.is_file() or art.stat().st_size == 0:
        stage["A_fail_absent_or_empty"] += 1
        d["A"] = False
        d["A_why"] = "absent_or_empty"
        detail[uid] = d
        state_dist["NO_ARTIFACT"] += 1
        continue
    try:
        doc = json.loads(art.read_text(encoding="utf-8"))
    except Exception as exc:
        stage["A_fail_unparseable"] += 1
        d["A"] = False
        d["A_why"] = "unparseable:" + type(exc).__name__
        detail[uid] = d
        state_dist["UNPARSEABLE"] += 1
        continue
    st = str(doc.get("state", "")).upper() if isinstance(doc, dict) else ""
    state_dist[st or "<none>"] += 1
    if not isinstance(doc, dict) or st in NOT_DELIVERING or not doc.get("sentinel"):
        stage["A_fail_selfblocked_or_no_sentinel"] += 1
        d["A"] = False
        d["A_why"] = "state=" + (st or "?") + " sentinel=" + str(bool(doc.get("sentinel") if isinstance(doc, dict) else False))
        detail[uid] = d
        continue
    d["A"] = True
    d["state"] = st
    stage["A_pass"] += 1

    # B manifest primary-row sha match
    man_p = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    ok_b = False
    if man_p.is_file():
        try:
            man = json.loads(man_p.read_text(encoding="utf-8"))
            rows = man.get("artifacts") or man.get("rows") or man.get("files") or []
            for row in rows:
                rp = str(row.get("path", "")).replace("\\", "/")
                if (row.get("role") == "primary" or rp == out_rel) and (REPO / rp).is_file():
                    ok_b = lf_sha(REPO / rp) == row.get("sha256")
                    break
        except Exception:
            ok_b = False
    d["B"] = ok_b
    if ok_b:
        stage["B_pass"] += 1
    else:
        stage["B_fail"] += 1
        d["B_why"] = "manifest_missing_or_sha_mismatch"
        detail[uid] = d
        continue

    # C schema
    ok_c = True
    why = []
    for s in schemas:
        try:
            errs = schema_resolver.validate_artifact(doc, s)
        except Exception as exc:
            errs = ["resolver:" + type(exc).__name__]
        if errs:
            ok_c = False
            why.append(s.split("/")[-1] + ":" + str(len(errs)))
    d["C"] = ok_c
    if ok_c:
        stage["C_pass"] += 1
    else:
        stage["C_fail"] += 1
        d["C_why"] = ",".join(why)
        detail[uid] = d
        continue

    # D admission
    ad = admit(doc)
    d["D"] = ad == "ACCEPT"
    if d["D"]:
        stage["D_pass"] += 1
    else:
        stage["D_fail"] += 1
        d["D_why"] = ad
        detail[uid] = d
        continue

    # E genuine independent reviewer
    rev = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else None
    rid = str((rev or {}).get("reviewer_id", ""))
    stamped = (not rev) or rid == uid + "-independent-reviewer" or "probe" in rid.lower() or "fabricated" in rid.lower()
    genuine = bool(rev) and rev.get("verdict") == "PASS" and rev.get("independent") is True and not stamped
    d["E"] = genuine
    d["reviewer_id"] = rid
    if genuine:
        stage["E_pass_full_green"] += 1
    else:
        stage["E_fail_stamped_or_absent"] += 1
    detail[uid] = d

out = {
    "census": "w4s6-r2 fleet census",
    "total_units": len(ids),
    "stage_funnel": dict(stage),
    "state_distribution": dict(state_dist),
    "full_green": stage["E_pass_full_green"],
    "detail": detail,
}
(REPO / "_reviewer-w4-shard6-r2" / "census_out.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("TOTAL", len(ids))
for k, v in sorted(stage.items()):
    print(k, v)
print("STATE_DIST", dict(state_dist))
print("FULL_GREEN", stage["E_pass_full_green"], "/", len(ids))
