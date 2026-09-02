#!/usr/bin/env python3
"""Probe 1: margin table validates and covers every metric the release gate reads."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.bench import margins, paths, release_gate, serialize  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scenario import CANDIDATE_WIN, comparison  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0301-probe1 {msg}")
    return 1


def main() -> int:
    inv = margins.load_inventory(root=REPO)
    tab = margins.load_margin_table(root=REPO)
    gate_ids = margins.gate_metric_ids(inv)
    if len(gate_ids) < 2:
        return fail(f"gate reads too few metrics: {gate_ids}")
    gaps = margins.coverage_gaps(inv, tab)
    if gaps:
        return fail(f"coverage gaps {gaps}")
    margins.assert_table_covers_gate(inv, tab)

    accepted = release_gate.schema_rejects_garbage(root=REPO)
    if accepted:
        return fail(f"schema accepted garbage {accepted}")

    checklist = (REPO / paths.CHECKLIST_REL).read_text(encoding="utf-8")
    for needle in (
        paths.MARGIN_TABLE_REL,
        tab["decided_at"],
        "NON_INFERIOR",
        "worse_delta <= margin",
        "POST_HOC_MARGIN_CHANGE",
    ):
        if needle not in checklist:
            return fail(f"checklist missing {needle!r}")

    bound = release_gate.bind_table(tab)
    rec = release_gate.evaluate(
        comparison("p1-win", CANDIDATE_WIN, bound),
        table=tab,
        inventory=inv,
        root=REPO,
    )
    if rec["verdict"] != "PASS":
        return fail(f"known-good win verdict={rec['verdict']} alarms={rec['alarms']}")

    dropped = deepcopy(tab)
    dropped["metrics"] = [m for m in dropped["metrics"] if m["id"] != "tokens_out"]
    rec_gap = release_gate.evaluate(
        comparison("p1-gap", CANDIDATE_WIN, release_gate.bind_table(dropped)),
        table=dropped,
        inventory=inv,
        root=REPO,
    )
    if rec_gap["verdict"] != "INVENTORY_GAP":
        return fail(f"missing tokens_out verdict={rec_gap['verdict']}")
    if not any("tokens_out" in a for a in rec_gap["alarms"]):
        return fail(f"gap alarms did not name tokens_out: {rec_gap['alarms']}")

    incomplete = comparison("p1-undef", CANDIDATE_WIN, bound)
    del incomplete["candidate"]["tool_calls"]
    rec_undef = release_gate.evaluate(
        incomplete, table=tab, inventory=inv, root=REPO
    )
    if rec_undef["verdict"] != "UNDEFINED_MARGIN":
        return fail(f"missing value verdict={rec_undef['verdict']}")

    unbound = comparison("p1-unbound", CANDIDATE_WIN, bound)
    unbound["margin_table_sha256"] = None
    rec_unbound = release_gate.evaluate(
        unbound, table=tab, inventory=inv, root=REPO
    )
    if rec_unbound["verdict"] != "UNBOUND":
        return fail(f"unbound verdict={rec_unbound['verdict']}")

    print(
        json.dumps(
            {
                "gate_metrics": gate_ids,
                "coverage_gaps": gaps,
                "table_sha256": bound,
                "decided_at": tab["decided_at"],
                "git_state": tab["git_state"],
                "known_good": rec["verdict"],
                "dropped_metric": rec_gap["verdict"],
                "missing_value": rec_undef["verdict"],
                "unbound": rec_unbound["verdict"],
                "schema_rejects_garbage": True,
                "checklist_cites_table": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"covered={len(gate_ids)}/{len(gate_ids)} "
        f"decided_at={tab['decided_at']} sha256={bound}"
    )
    print("SUCCESS:TST-0301-probe1 margin table covers every gate metric")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
