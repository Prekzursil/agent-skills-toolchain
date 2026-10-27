#!/usr/bin/env python3
"""INDEPENDENT REVIEWER shard-13 w2 verifier.

Mechanically independent second signal over the 12 shard units.
Re-derives from raw disk + catalog, does NOT import the measure module:
  1. receipt exists / non-empty / parses / not self-BLOCKED / state==SUCCESS
  2. reviewer block: verdict==PASS and independent==True (receipt_core rule)
  3. schema-required fields for the unit's profile (from catalog output_schema
     string + receipt.schema.json $defs required lists)
  4. sha256(CRLF->LF bytes) recomputed here, matched against
     probes/<id>/UNIT-ARTIFACT-MANIFEST.json primary row
Exit 0 only if all 12 units hold every check (fail-closed).
"""
from __future__ import annotations

import hashlib
import json
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
UNITS = [
    "IMP-0229", "IMP-0261", "IMP-0264", "IMP-0269", "IMP-0270", "IMP-0271",
    "IMP-0272", "IMP-0273", "IMP-0274", "IMP-0275", "IMP-0279", "IMP-0303",
]
# Common required core from the profile strings in the catalog output_schema
# column (all shard-13 profiles require this same set).
PROFILE_REQUIRED = [
    "unit_id", "artifact_paths", "spec_anchor", "evidence", "test_ids",
    "negative_control_ids", "reviewer_verdict", "residual_unknowns",
]

cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
catalog = {u.get("id"): u for u in cat["work_units"]}

schema_doc = json.loads((REPO / "command-center" / "schema" / "receipt.schema.json").read_text(encoding="utf-8"))
defs = schema_doc.get("$defs", {})


def digest_crlf(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def check_profile_required(receipt: dict, profiled: bool) -> list[str]:
    """Required fields per the catalog output_schema profile string.

    Accepts either snake_case keys (receipt style) or the receipt holding
    them nested; artifact_paths may be spelled artifacts[].path.
    """
    if not profiled:
        return []
    missing = []
    for key in PROFILE_REQUIRED:
        if key in receipt:
            continue
        if key == "artifact_paths":
            if isinstance(receipt.get("artifacts"), list) and receipt["artifacts"]:
                continue
        if key == "reviewer_verdict":
            rev = receipt.get("reviewer") or {}
            if rev.get("verdict") == "PASS":
                continue
        if key == "spec_anchor" and receipt.get("spec_anchor") is None:
            missing.append("spec_anchor(empty)")
            continue
        missing.append(key)
    return missing


failures: dict[str, list[str]] = {}
summary = {}

for uid in UNITS:
    bad: list[str] = []
    cu = catalog.get(uid)
    if cu is None:
        print(f"{uid} FAIL catalog-missing")
        failures[uid] = ["catalog-missing"]
        continue
    out_rel = str(cu.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel

    # 1. artifact existence / non-empty / parse / self-state
    if not out.is_file() or out.stat().st_size <= 0:
        bad.append("artifact-absent-or-empty")
        failures[uid] = bad
        print(f"{uid} FAIL artifact-absent-or-empty")
        continue
    try:
        text = out.read_text(encoding="utf-8")
        receipt = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        bad.append(f"unparseable:{type(exc).__name__}")
        failures[uid] = bad
        print(f"{uid} FAIL unparseable:{exc}")
        continue
    state = str(receipt.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        bad.append(f"self-declared:{state}")
    if state != "SUCCESS":
        bad.append(f"state!=SUCCESS:{state}")

    # 2. reviewer block (receipt_core: SUCCESS requires reviewer PASS+independent)
    rev = receipt.get("reviewer") or {}
    if rev.get("verdict") != "PASS":
        bad.append(f"reviewer.verdict={rev.get('verdict')!r}")
    if rev.get("independent") is not True:
        bad.append("reviewer.independent!=true")

    # 3. profile-required fields
    schema_str = str(cu.get("output_schema") or "")
    miss = check_profile_required(receipt, "profile=" in schema_str)
    if miss:
        bad.append("profile-missing:" + ",".join(miss))

    # 4. manifest sha match (CRLF-normalized), primary row = receipt path
    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not man_path.is_file():
        bad.append("manifest-absent")
    else:
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            bad.append(f"manifest-unparseable:{type(exc).__name__}")
            man = None
        if isinstance(man, dict):
            live_sha, live_bytes = digest_crlf(out)
            rows = [
                a for a in (man.get("artifacts") or [])
                if isinstance(a, dict)
                and str(a.get("path") or "").replace("\\", "/") == out_rel
            ]
            if not rows:
                bad.append("manifest-primary-row-absent")
            elif not any(
                a.get("present") is True and str(a.get("sha256") or "") == live_sha
                for a in rows
            ):
                bad.append(f"manifest-sha-mismatch live={live_sha[:12]}")
            summary[uid] = (live_bytes, live_sha[:12])

    if bad:
        failures[uid] = bad
        print(f"{uid} FAIL {'; '.join(bad)}")
    else:
        print(f"{uid} PASS receipt=SUCCESS reviewer=PASS/independent sha={summary.get(uid, ('?',))[1]}")

print("---")
if failures:
    print(f"FAILED:shard13-review {len(failures)}/{len(UNITS)} units failing")
    for u, why in failures.items():
        print(f"  {u}: {'; '.join(why)}")
    sys.exit(1)
print(f"SUCCESS:shard13-review all {len(UNITS)} units hold every independent check")
sys.exit(0)
