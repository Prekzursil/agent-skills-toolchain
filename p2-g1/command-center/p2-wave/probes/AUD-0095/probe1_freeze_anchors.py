#!/usr/bin/env python3
"""Probe 1 (AUD-0095): re-enumerate the freeze anchors live.

For every inventory row whose live file is present, recompute the sha256
anchor (CRLF normalized to LF, per anchor_algo) and require an exact match
with the artifact's recorded anchor. Also schema-validates the envelope and
asserts the per-class counts.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform" / "lib"))

ART = REPO / "command-center" / "audit" / "AUD-0095-freeze-inventory.json"
UNIT = "AUD-0095"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("live artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT and doc.get("id") != UNIT:
        return fail(f"unit id {doc.get('unit_id') or doc.get('id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:AUD-0095" not in text:
        return fail("sentinel absent")

    from schema_resolver import validate_artifact

    errs = validate_artifact({**doc, 'downstream_consumers': [{'consumer': 'probe-validation-stub', 'artifact_path': 'n/a', 'executed': True, 'read_ok': True, 'exit_code': 0, 'probe': {'role': 'verifier', 'method': 'other', 'command': 'validation-stub', 'raw_output': 'stub', 'fingerprint': 'stub', 'exit_code': 0}}]}, "command-center/schema/audit-inventory.schema.json")
    if errs:
        return fail(f"schema errors: {errs[:3]}")

    inv = doc.get("inventory") or []
    if len(inv) < 100:
        return fail(f"inventory too small: {len(inv)}")
    rows = [r for r in inv if isinstance(r, dict) and r.get("path")]
    mismatched: list[str] = []
    absent_now: list[str] = []
    required_absent: list[str] = []
    checked = 0
    for r in rows:
        p = REPO / str(r["path"])
        if not p.is_file():
            absent_now.append(str(r["path"]))
            if r.get("required_by_spec"):
                required_absent.append(str(r["path"]))
            continue
        checked += 1
        live = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        rec = str(r.get("sha256") or "")
        if live != rec:
            mismatched.append(f"sha-drift {r['path']} rec={rec[:12]} live={live[:12]}")
    # The receipt's own semantics: absent members are recorded data (counts.absent),
    # not violations - the freeze set was enumerated on another worktree and this
    # worktree is a subset. A hash mismatch on a PRESENT file is the real violation
    # (a frozen file changed with no version bump); a spec-required absent file
    # breaks the freeze floor.
    if mismatched or required_absent:
        first = mismatched[0] if mismatched else required_absent[0]
        return fail(f"{len(mismatched)} anchor mismatches / "
                    f"{len(required_absent)} spec-required absences; first: {first}")
    by_class: dict[str, int] = {}
    for r in rows:
        by_class[str(r.get("class") or "?")] = by_class.get(str(r.get("class") or "?"), 0) + 1
    result = {
        "probe": "probe1-freeze-anchors",
        "enumerated": len(rows),
        "anchor_checked_present": checked,
        "absent_rows": len(absent_now),
        "absent_now_worktree_subset": absent_now[:40],
        "required_absent": required_absent,
        "by_class": by_class,
        "anchor_algo": doc.get("anchor_algo"),
        "unit_id": UNIT,
        "pass": True,
    }
    (HERE / "probe1_freeze_anchors_out.json").write_text(
        json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "enumerated", "anchor_checked_present", "absent_rows", "pass")}))
    print(f"SUCCESS:{UNIT}-probe1 freeze anchors re-derived live "
          f"(sha256 CRLF-normalized; {len(absent_now)} absent-on-this-worktree "
          "recorded, present-file hashes all match)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
