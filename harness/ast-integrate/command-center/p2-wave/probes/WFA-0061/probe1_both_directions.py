#!/usr/bin/env python3
"""Probe 1: both set differences, both-states direction drop, no invented 108."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import coverage as CV  # noqa: E402
import sources as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0061-mechanism-coverage-gaps.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0061-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    if doc.get("unit_id") != "WFA-0061":
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0061" not in text:
        return fail("sentinel-absent")

    corpus = C.load_corpus()
    C.materialize_bodies(corpus)
    live = S.inventory(REPO)
    worktree_docs = CV.load_worktree_docs(REPO, live.get("worktree_observed") or [])
    computed = CV.compute(corpus, live, worktree_docs)
    inc = computed["incidence"]

    if not computed["both_directions_published"]:
        return fail("recomputed both-directions false")
    if not doc.get("both_directions_published"):
        return fail("artifact both-directions false")
    if not doc.get("uncovered_mechanisms") or not doc.get("empty_blueprints"):
        return fail("artifact missing a gap list")
    if computed["uncovered_mechanisms"] != doc.get("uncovered_mechanisms"):
        return fail("uncovered mismatch vs artifact")
    if computed["empty_blueprints"] != doc.get("empty_blueprints"):
        return fail("empty_blueprints mismatch vs artifact")

    dropped = CV.suppress_direction(inc, "empty_blueprints")
    if CV.both_directions_published(dropped):
        return fail("dropping empty_blueprints still counted as both directions")
    dropped_u = CV.suppress_direction(inc, "uncovered_mechanisms")
    if CV.both_directions_published(dropped_u):
        return fail("dropping uncovered_mechanisms still counted as both directions")
    if not CV.both_directions_published(inc):
        return fail("intact incidence failed both-directions")

    if live.get("invented_108_blueprints") or doc.get("live_sources", {}).get(
        "invented_108_blueprints"
    ):
        return fail("invented 108 blueprints")
    if inc["n_blueprints"] == 108:
        return fail("fixture padded to 108")
    if live.get("library_108_enumerated") is True and not (
        live.get("live_blueprint_library") or {}
    ).get("present"):
        return fail("library_108_enumerated true without a file")
    if doc.get("counts", {}).get("live_108_enumerated") != live.get(
        "library_108_enumerated"
    ):
        return fail("live_108_enumerated mismatch")

    if computed["namespaces"]["collision"]:
        return fail("id namespace collision")
    if not computed["namespaces"]["prefix_ok"]:
        return fail("id prefix not closed")

    n_cells = inc["n_cells"]
    want_cells = inc["n_candidates"] + inc["n_blueprints"]
    want_cells *= len(inc["row_ids"])
    if n_cells != want_cells:
        return fail(f"cell count {n_cells} != {want_cells}")
    if inc["n_evidenced"] + inc["n_honest_null"] != n_cells:
        return fail("EVIDENCED+HONEST-NULL does not cover every cell")

    payload = {
        "pass": True,
        "probe": "probe1-both-directions",
        "unit_id": "WFA-0061",
        "uncovered_n": len(computed["uncovered_mechanisms"]),
        "empty_blueprints_n": len(computed["empty_blueprints"]),
        "both_directions": True,
        "drop_empty_fails": True,
        "drop_uncovered_fails": True,
        "intact_passes": True,
        "fixture_blueprints": inc["n_blueprints"],
        "live_108_enumerated": live.get("library_108_enumerated"),
        "invented_108": False,
        "n_cells": n_cells,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"uncovered={payload['uncovered_n']} empty_bp={payload['empty_blueprints_n']} "
        f"fixture_bp={inc['n_blueprints']} live_108={live.get('library_108_enumerated')}"
    )
    print("SUCCESS:WFA-0061-probe1 both directions and no invented 108")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
