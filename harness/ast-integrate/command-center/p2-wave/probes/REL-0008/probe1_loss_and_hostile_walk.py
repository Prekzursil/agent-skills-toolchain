#!/usr/bin/env python3
"""Named probe 1: hostile-path walk + plant-and-delete loss detection.

Signal 1 is the census identity set (exact relative paths, NUL hashed,
260+ path hashed). Signal 2 is oracle loss on a broken install that
deletes a seeded owner file. Probe 2 uses a different lifecycle path
(case-insensitive uninstall) and skip-accounting.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lifecycle import INSTALL_DECLARED, apply_install, apply_install_deletes_owner  # noqa: E402
from oracle import run_op  # noqa: E402
from profile import (  # noqa: E402
    CASE_OWNER_REL,
    CASE_PACKAGE_REL,
    KEEP_REL,
    RESERVED_REL,
    fresh_profile,
)
from walker import casefold_collapsed, census, hashed_only  # noqa: E402

ART = REPO / "command-center/receipts/REL-0008.json"


def fail(msg: str) -> int:
    print(f"FAILED:REL-0008-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "REL-0008":
        return fail(f"unit_id={doc.get('unit_id')}")
    if "SUCCESS:REL-0008" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    src = (HERE / "walker.py").read_text(encoding="utf-8")
    if "os.path.relpath" in src:
        return fail("walker.py contains os.path.relpath")

    with fresh_profile() as (root, _info, seed):
        snap = census(root)
        hashed = hashed_only(snap)
        nul = hashed.get(RESERVED_REL)
        long_row = hashed.get(seed["long_rel"])
        if nul is None or nul.get("skipped"):
            return fail("NUL missing or skipped")
        if long_row is None or long_row.get("skipped"):
            return fail("long path missing or skipped")
        if long_row["rel_chars"] < 260:
            return fail(f"long rel_chars={long_row['rel_chars']} want>=260")
        fifo = snap.get(seed["fifo_rel"]) or {}
        if not fifo.get("skipped"):
            return fail("fifo not NOT-CHECKED")

        apply_install(root)
        after = hashed_only(census(root))
        if CASE_OWNER_REL not in after or CASE_PACKAGE_REL not in after:
            return fail("case siblings not both tracked")
        if after[CASE_OWNER_REL]["sha256"] == after[CASE_PACKAGE_REL]["sha256"]:
            return fail("case siblings unexpectedly byte-identical")
        collapsed = casefold_collapsed(after)
        if len(collapsed) >= len(after):
            return fail("casefold collapse did not drop a sibling")

    with fresh_profile() as (root, _info, _seed):
        planted = run_op(
            root,
            "install-deletes-owner",
            lambda p: apply_install_deletes_owner(p, KEEP_REL),
            INSTALL_DECLARED,
        )
    lost = [row["path"] for row in planted.loss]
    if KEEP_REL not in lost or planted.silent:
        return fail(f"plant-and-delete not caught lost={lost}")

    report = doc.get("report") or {}
    if report.get("kind") != "lifecycle-drill-receipt":
        return fail(f"report.kind={report.get('kind')}")
    recorded = report.get("plant_and_delete") or {}
    if KEEP_REL not in (recorded.get("lost_paths") or []):
        return fail("receipt plant-and-delete lost_paths drift")
    hostile = report.get("hostile_walk") or {}
    if not hostile.get("nul_present") or hostile.get("nul_skipped"):
        return fail("receipt hostile_walk NUL drift")
    if hostile.get("nul_sha256") != nul["sha256"]:
        return fail("receipt NUL sha256 drift")

    out = {
        "probe": "probe1-loss-and-hostile-walk",
        "unit_id": "REL-0008",
        "nul_hashed": True,
        "long_rel_chars": long_row["rel_chars"],
        "case_exact_count": len(after),
        "casefold_collapsed_count": len(collapsed),
        "plant_delete_caught": True,
        "lost_path": KEEP_REL,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"nul_hashed=True long_rel_chars={long_row['rel_chars']} "
        f"exact={len(after)} collapsed={len(collapsed)} lost={KEEP_REL}"
    )
    print("SUCCESS:REL-0008-probe1 hostile walk and plant-and-delete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
