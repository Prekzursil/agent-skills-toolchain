#!/usr/bin/env python3
"""Probe 1: every declaration resolves to path+run_id or is marked unresolved.

Planted control: a suite registered with a fake control path must be flagged
path_missing and must not count as covered.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402

ART = REPO / "command-center/receipts/TST-0327.json"
PLANTED = "suite.planted-ghost"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0327-probe1 {msg}")
    return 1


def check_artifact_if_present() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0327" not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    counts = doc.get("counts") or doc.get("fixture_counts") or {}
    if not isinstance(counts, dict):
        return "artifact missing fixture three-counts"
    for key in ("no_declared_control", "declared_never_failed", "observed_failing"):
        if key not in counts:
            return f"artifact counts missing {key}"
    return None


def main() -> int:
    art_err = check_artifact_if_present()
    if art_err:
        return fail(art_err)

    report = C.fixture_census(REPO)
    if not C.every_declaration_resolved_or_unresolved(report):
        return fail("a declaration was neither fully_resolved nor unresolved")

    by_id = {row["suite_id"]: row for row in report["rows"]}
    planted = by_id.get(PLANTED)
    if planted is None:
        return fail("planted ghost suite missing from census")
    if not planted.get("planted_path_missing"):
        return fail("planted fake control path was not flagged")
    if planted.get("counts_as_covered"):
        return fail("planted ghost suite counted as covered")
    if planted.get("bucket") != "declared_never_failed":
        return fail(f"planted bucket={planted.get('bucket')}")
    decls = planted.get("declarations") or []
    if not decls or decls[0].get("status") != C.PATH_MISSING:
        return fail(f"planted declaration status={decls[0].get('status') if decls else None}")
    if decls[0].get("resolved_path") is not None:
        return fail("planted ghost resolved to a path")
    if decls[0].get("run_id"):
        return fail("planted ghost invented a run id")

    none = by_id.get("suite.none")
    if none is None or none.get("bucket") != C.NO_DECLARED:
        return fail("suite.none was not bucketed as no_declared_control")

    covered = by_id.get("suite.covered")
    if covered is None or not covered.get("counts_as_covered"):
        return fail("suite.covered was not counted as covered")
    cov_decl = (covered.get("declarations") or [None])[0]
    if not cov_decl or not cov_decl.get("resolved_path") or not cov_decl.get("run_id"):
        return fail("covered suite missing path+run_id")
    if cov_decl.get("unresolved"):
        return fail("covered suite marked unresolved")

    never_run = by_id.get("suite.never-run")
    if never_run is None or never_run.get("counts_as_covered"):
        return fail("never-run control counted as covered")
    pass_only = by_id.get("suite.pass-only")
    if pass_only is None or pass_only.get("counts_as_covered"):
        return fail("pass-only control counted as covered")

    counts = report["counts"]
    if counts["n_suites"] != 5:
        return fail(f"expected 5 fixture suites, got {counts['n_suites']}")
    if not counts["sum_equals_n"]:
        return fail("three counts do not sum to n_suites")
    if counts["no_declared_control"] != 1:
        return fail(f"no_declared_control={counts['no_declared_control']}")
    if counts["declared_never_failed"] != 3:
        return fail(f"declared_never_failed={counts['declared_never_failed']}")
    if counts["observed_failing"] != 1:
        return fail(f"observed_failing={counts['observed_failing']}")
    if counts["covered"] != counts["observed_failing"]:
        return fail("covered diverged from observed_failing")

    live = C.live_registry_census(REPO)
    if live["registry_present"] and not C.every_declaration_resolved_or_unresolved(live):
        return fail("live registry declaration neither resolved nor unresolved")

    out = {
        "probe": "probe1-resolution-and-planted",
        "unit_id": "TST-0327",
        "pass": True,
        "counts": counts,
        "planted_suite": PLANTED,
        "planted_flagged": True,
        "planted_status": decls[0]["status"],
        "every_declaration_resolved_or_unresolved": True,
        "covered_run_id": cov_decl["run_id"],
        "covered_path": cov_decl["resolved_path"],
        "live_registry_present": live["registry_present"],
        "live_counts": live.get("counts"),
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "planted_flagged=True covered=1 never_failed=3 none=1 "
        f"live_registry_present={live['registry_present']}"
    )
    print("SUCCESS:TST-0327-probe1 census resolves declarations; planted ghost flagged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
