#!/usr/bin/env python3
"""Named probe 1: three catalog controls + archive refusal + both-states LOST.

Control: plant a synthetic deleted symbol that exists nowhere → LOST.
Control: a symbol that moved into tools/lib/ → PRESERVED with new path cited.
Control: a deleted TEST whose assertion has no equivalent → LOST-COVERAGE,
not only a lost file.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from analyze import analyze  # noqa: E402
from classify import classify_element, index_retained  # noqa: E402
from recover import refuse_archive  # noqa: E402
from scenario import (  # noqa: E402
    COVERAGE_TOKEN,
    LOST_PATH,
    LOST_SYMBOL,
    LOST_TEST_PATH,
    PRESERVED_PATH,
    PRESERVED_SYMBOL,
)

ART = REPO / "command-center/receipts/BLD-0035.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:BLD-0035-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "BLD-0035":
        print("FAILED:BLD-0035-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:BLD-0035" not in json.dumps(doc):
        print("FAILED:BLD-0035-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:BLD-0035-probe1 self-declared", doc.get("state"))
        return 1

    scratch = Path(tempfile.mkdtemp(prefix="bld0035-p1-"))
    try:
        result = analyze(scratch)
        model = result["model"]
        ctrl = result["controls"]
        if ctrl["lost_unique"] is None:
            print("FAILED:BLD-0035-probe1 unique symbol was not LOST")
            return 1
        if ctrl["preserved_moved"] is None:
            print("FAILED:BLD-0035-probe1 moved symbol was not PRESERVED with tools/lib path")
            return 1
        if ctrl["lost_coverage"] is None:
            print("FAILED:BLD-0035-probe1 unique test was not LOST-COVERAGE")
            return 1
        cov = ctrl["lost_coverage"]
        if cov["classification"] == "LOST":
            print("FAILED:BLD-0035-probe1 coverage classified as lost file, not lost coverage")
            return 1

        archive = refuse_archive(model["git_dir"], model["commit_oid"], LOST_PATH)
        if not archive["refused"]:
            print("FAILED:BLD-0035-probe1 git archive was not refused")
            print(archive)
            return 1

        # Both-states: copy the lost symbol into a retained clone → PRESERVED.
        retained_bad = scratch / "retained-with-lost"
        if retained_bad.exists():
            shutil.rmtree(retained_bad)
        shutil.copytree(model["retained_root"], retained_bad)
        planted = retained_bad / "tools/lib/planted-lost.mjs"
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_text(
            f'export function {LOST_SYMBOL}() {{ return "planted"; }}\n',
            encoding="utf-8",
        )
        flipped = classify_element(
            {
                "path": LOST_PATH,
                "kind": "export",
                "symbol": LOST_SYMBOL,
                "token": LOST_SYMBOL,
            },
            index_retained(retained_bad),
        )
        if flipped["classification"] != "PRESERVED":
            print("FAILED:BLD-0035-probe1 both-states did not flip LOST→PRESERVED")
            print(flipped)
            return 1
        if "tools/lib/planted-lost.mjs" not in str(flipped.get("retained_path") or ""):
            print("FAILED:BLD-0035-probe1 both-states retained_path not cited")
            print(flipped)
            return 1

        recorded = doc.get("controls") or []
        want = {
            "C-lost-unique": "LOST",
            "C-preserved-tools-lib": "PRESERVED",
            "C-lost-coverage": "LOST-COVERAGE",
        }
        by_id = {r.get("id"): r for r in recorded if isinstance(r, dict)}
        for cid, cls in want.items():
            row = by_id.get(cid)
            if not row or row.get("classification") != cls or row.get("result") != "PASS":
                print(f"FAILED:BLD-0035-probe1 artifact control {cid} {row}")
                return 1

        surfaces = doc.get("surfaces") or []
        art_lost = [
            s
            for s in surfaces
            if s.get("path") == LOST_PATH and s.get("symbol") == LOST_SYMBOL
        ]
        art_pres = [
            s
            for s in surfaces
            if s.get("path") == PRESERVED_PATH
            and s.get("symbol") == PRESERVED_SYMBOL
        ]
        art_cov = [
            s
            for s in surfaces
            if s.get("path") == LOST_TEST_PATH
            and s.get("classification") == "LOST-COVERAGE"
        ]
        if not art_lost or art_lost[0].get("classification") != "LOST":
            print("FAILED:BLD-0035-probe1 artifact lost row mismatch")
            return 1
        if (
            not art_pres
            or art_pres[0].get("classification") != "PRESERVED"
            or "tools/lib/net-allowlist.mjs"
            not in str(art_pres[0].get("retained_path") or "").replace("\\", "/")
        ):
            print("FAILED:BLD-0035-probe1 artifact preserved row mismatch")
            return 1
        if not art_cov or COVERAGE_TOKEN not in json.dumps(art_cov):
            print("FAILED:BLD-0035-probe1 artifact coverage row mismatch")
            return 1

        out = {
            "probe": "probe1-controls",
            "unit_id": "BLD-0035",
            "lost_unique": True,
            "preserved_tools_lib": True,
            "lost_coverage": True,
            "archive_refused": True,
            "both_states_flip": True,
            "deleted_paths": result["counts"]["deleted_paths"],
            "trees": result["counts"]["trees"],
            "pass": True,
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"lost={LOST_SYMBOL} preserved={PRESERVED_SYMBOL} "
            f"coverage={COVERAGE_TOKEN} archive_refused=True"
        )
        print("SUCCESS:BLD-0035-probe1 catalog controls and archive refusal")
        return 0
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
