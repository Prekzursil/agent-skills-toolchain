#!/usr/bin/env python3
"""Probe 2: independent 34/108 recount + foundry consumers clean + reviewer.

Signal A is JSON field membership. Signal B is a raw-file regex that matches
the key ``state`` and not ``state_v``. Foundry gate/filter/report must lint
clean. Reviewer re-runs both-states without reading author prose.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FOUNDRY = REPO / "command-center" / "foundry"
sys.path.insert(0, str(FOUNDRY))
sys.path.insert(0, str(HERE))

import lint_field_contract as lint  # noqa: E402
from corpus import library_on_disk, load_blueprints  # noqa: E402
from recount import assert_catalog  # noqa: E402
from reviewer import review  # noqa: E402

ART = REPO / "command-center/foundry/WFA-0157-machine-consumer-field-contract-gate-on-state-v-size.json"
CONSUMERS = FOUNDRY / "consumers"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0157-probe2 {msg}")
    return 1


def main() -> int:
    lib = library_on_disk(REPO)
    print(f"library_on_this_worktree={bool(lib)} path={lib}")
    recount = assert_catalog()
    a, b = recount["signal_a"], recount["signal_b"]
    print(
        f"json n={a['n']} vocab_exact={a['vocab_exact']} "
        f"non_literal={a['non_literal']} distinct={a['distinct_literals']}"
    )
    print(
        f"regex n={b['n']} vocab_exact={b['vocab_exact']} "
        f"non_literal={b['non_literal']} distinct={b['distinct_literals']}"
    )
    print(f"signals_agree={recount['signals_agree']} matches_catalog={recount['matches_catalog_claim']}")
    if a["n"] != 108 or a["non_literal"] != 34 or a["vocab_exact"] != 74:
        return fail("json recount is not 34/74/108")
    if b["n"] != 108 or b["non_literal"] != 34:
        return fail("regex recount is not 34/108")
    if a["distinct_literals"] != 36:
        return fail("distinct state literals is not 36")

    records = load_blueprints()
    sys.path.insert(0, str(CONSUMERS))
    import filter as F  # noqa: E402
    import gate as G  # noqa: E402
    import report as R  # noqa: E402

    admitted = G.admitted(records)
    print(f"gate_admitted={len(admitted)} of {len(records)}")
    if len(admitted) != 108:
        return fail("gate reading state_v did not admit every decomposed record")
    tallies = R.tally_state_v(records)
    print(f"report_state_v={tallies}")
    if set(tallies) - {"FOUND", "REPAIRED", "MERGED", "NEW"}:
        return fail("report grouped a non-vocab state_v")
    sized = F.by_size_v(records, "M")
    print(f"filter_size_v_M={len(sized)}")
    if not sized:
        return fail("size_v filter returned empty")

    foundry = lint.lint_paths(lint.iter_py(CONSUMERS))
    print(f"foundry_consumer_lint_findings={len(foundry)}")
    if foundry:
        return fail("foundry gate/filter/report still read a gloss field")

    rev = review()
    print(
        f"reviewer_verdict={rev['verdict']} both_states={rev['executed_both_states']} "
        f"non_literal={rev['recount_non_literal']}"
    )
    if rev["verdict"] != "PASS":
        return fail("reviewer did not PASS")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    rc = doc.get("recount") or {}
    if int(rc.get("non_literal") or -1) != 34 or int(rc.get("n") or -1) != 108:
        return fail("artifact recount drifted from live 34/108")
    if doc.get("library", {}).get("on_this_worktree") is True and not lib:
        return fail("artifact claimed live library that is absent")
    if "SUCCESS:WFA-0157" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    print("SUCCESS:WFA-0157-probe2 recount-34-of-108 foundry-consumers reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
