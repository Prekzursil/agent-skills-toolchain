#!/usr/bin/env python3
"""Probe 1: unpinned devDep, exit-127 TOOL-MISSING, transitive two-level gap."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from classify import classify_scanner_exit, naive_scanner_exit  # noqa: E402
from scanner import classify_missing_scanner  # noqa: E402
from walk import transitive_control, unpinned_control  # noqa: E402

UNPINNED = HERE / "fixtures" / "unpinned" / "package.json"
GAP_LOCK = HERE / "fixtures" / "transitive-gap" / "package-lock.json"
CLEAN_LOCK = HERE / "fixtures" / "transitive-clean" / "package-lock.json"
ART = REPO / "command-center" / "receipts" / "BLD-0053.json"
SENTINEL = "SUCCESS:BLD-0053"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0053-probe1 {msg}")
    return 1


def main() -> int:
    unp = unpinned_control(UNPINNED)
    print("unpinned " + json.dumps({k: unp[k] for k in ("found", "gaps", "kind", "spec") if k in unp}, sort_keys=True))
    if not unp.get("found"):
        return fail("unpinned * devDependency not reported")
    if unp.get("kind") != "devDependencies" or unp.get("spec") != "*":
        return fail(f"unpinned kind/spec {unp}")
    needed = {
        "NO-PIN",
        "NO-LOCKFILE-HASH",
        "NO-PROVENANCE",
        "NO-LICENSE-RECORD",
        "NO-SBOM-ENTRY",
        "NO-ADVISORY-QUERY",
    }
    if set(unp.get("gaps") or []) != needed:
        return fail(f"unpinned gaps {unp.get('gaps')}")

    miss = classify_missing_scanner()
    print(
        f"exit127 returncode={miss['returncode']} "
        f"author={miss['author']} naive={miss['naive']}"
    )
    if miss["returncode"] != 127:
        return fail(f"missing scanner exit {miss['returncode']}")
    if classify_scanner_exit(127) != "TOOL-MISSING":
        return fail("127 did not classify TOOL-MISSING")
    if naive_scanner_exit(127) != "CLEAN":
        return fail("naive control did not map 127 to CLEAN")
    if miss["author"] != "TOOL-MISSING" or miss["naive"] != "CLEAN":
        return fail(f"127 author/naive {miss}")
    if classify_scanner_exit(0) != "CLEAN" or classify_scanner_exit(1) != "FINDINGS":
        return fail("0/1 classes drifted")

    trans = transitive_control(GAP_LOCK)
    print(
        "transitive "
        + json.dumps(
            {
                "direct_only": trans.get("direct_only"),
                "leaf_depth": trans.get("leaf_depth"),
                "leaf_in_direct": trans.get("leaf_in_direct"),
                "leaf_integrity": trans.get("leaf_integrity"),
            },
            sort_keys=True,
        )
    )
    if trans.get("direct_only") != ["mid-pkg"]:
        return fail(f"direct_only {trans.get('direct_only')}")
    if trans.get("leaf_depth") != 2:
        return fail(f"leaf_depth {trans.get('leaf_depth')} (walk is not transitive)")
    if trans.get("leaf_in_direct") is not False:
        return fail("leaf listed as direct")
    if trans.get("leaf_integrity") is not None:
        return fail(f"gap fixture leaf has integrity {trans.get('leaf_integrity')}")

    clean = transitive_control(CLEAN_LOCK)
    if clean.get("leaf_depth") != 2 or not clean.get("leaf_integrity"):
        return fail(f"clean fixture both-states {clean}")

    if ART.is_file() and ART.stat().st_size > 0:
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            return fail(f"self-declared {doc.get('state')}")
        if SENTINEL not in text:
            return fail("sentinel-absent")

    print("SUCCESS:BLD-0053-probe1 unpinned 127 transitive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
