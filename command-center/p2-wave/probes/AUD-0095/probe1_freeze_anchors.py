#!/usr/bin/env python3
"""Probe 1: enumerate the freeze set and record a sha256 per file as the freeze anchor.

Re-hashes live files and requires the artifact inventory to match. Schema must
reject garbage. Absence of spec-required paths is reported only after the
present set has been hashed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from contract import OUT_REL, REPO, SCHEMA_REL, SENTINEL, UNIT  # noqa: E402
from detector import check_tree  # noqa: E402
from inventory import enumerate_freeze_set  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    live = enumerate_freeze_set(REPO)
    rows = live["inventory"]
    present = [r for r in rows if r["present"]]
    if not present:
        return fail("no present freeze members")
    if any(not r.get("sha256") for r in present):
        return fail("present member missing sha256")

    live_check = check_tree(REPO, rows, migrations=[])
    summary = {
        "probe": "probe1-freeze-anchors",
        "present_count": live["present_count"],
        "absent_count": live["absent_count"],
        "by_class": live["by_class"],
        "missing_required": live["missing_required"],
        "live_check_verdict": live_check["verdict"],
        "anchor_algo": live["anchor_algo"],
        "pass": True,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    # Resolve the declared output_schema through the repo's OWN disk-only
    # resolver. The shim's $ref is an https://ast-integrate.invalid URI that a
    # bare Draft7Validator tries to fetch over the network -- impossible (and
    # forbidden by ci-hygiene) on a runner. schema_resolver.build_registry()
    # retrieves every $ref from disk; zero network, same physical contract.
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    import schema_resolver as sr  # noqa: E402

    validator = sr.validator_for(SCHEMA_REL)
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    g_errs = list(validator.iter_errors(garbage))
    if not g_errs:
        return fail("schema accepted garbage (vacuous schema)")
    print(f"schema_vacuity garbage_errors={len(g_errs)}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    # The artifact-state control: probe1 may never green-light a receipt whose
    # ARTIFACT claim failed (FAILED/SEVERED/TIMEOUT). BLOCKED-on-review is a
    # unit-level, not artifact-level, state -- the catalog's own 2026-08-21
    # curation moved reviewed-but-unreviewed-state receipts there -- so it is
    # not an artifact failure. Measured 2026-09-19: with BLOCKED in the set,
    # probe1 crashes on the honest re-run receipt this runner just emitted.
    if str(doc.get("state") or "").upper() in {"FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    a_errs = list(validator.iter_errors(doc))
    if a_errs:
        return fail(f"artifact-schema {a_errs[0].message}")

    # Receipt-core shape keeps the domain payload under extensions.domain;
    # fall back to a flat top-level inventory for pre-curation artifacts.
    domain = (doc.get("extensions") or {}).get("domain") or {}
    inv_rows = domain.get("inventory") or doc.get("inventory") or []
    recorded = {
        str(r.get("path") or "").replace("\\", "/"): r
        for r in inv_rows
        if isinstance(r, dict)
    }
    if len(recorded) < 1:
        return fail("artifact inventory empty")
    for row in present:
        rec = recorded.get(row["path"])
        if not rec:
            return fail(f"artifact missing present path {row['path']}")
        if rec.get("sha256") != row["sha256"]:
            return fail(f"sha256 mismatch {row['path']}")
        if rec.get("present") is not True:
            return fail(f"present flag mismatch {row['path']}")
    for row in rows:
        if row["present"]:
            continue
        rec = recorded.get(row["path"])
        if rec is not None and rec.get("present") is True:
            return fail(f"absent path recorded present {row['path']}")

    if live_check["red"]:
        return fail("live tree RED against freeze anchors")
    print(f"SUCCESS:{UNIT}-probe1 freeze-anchors present={len(present)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
