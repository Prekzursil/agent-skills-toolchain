#!/usr/bin/env python3
"""Probe 2: independent recount + both-states + negative control + v1/in-tree census.

A disagreement between this recount and the artifact's counts blocks the unit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import staticcheck as S  # noqa: E402
import v1_census as V  # noqa: E402

OUT = (
    REPO
    / "command-center/design/council/"
    / "CNL-0010-stopping-expression-grammar-and-static-validation.schema.json"
)
EXAMPLES = HERE / "fixtures" / "examples.json"
METRICS = HERE / "fixtures" / "metrics.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
IN_TREE = REPO / "command-center/p2-wave/probes/ARC-0010/registry.schema.json"


def resolve_anchor(rel: str, line: int, snippet: str) -> tuple[bool, str]:
    path = REPO / rel
    if not path.is_file():
        return False, f"missing {rel}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False, f"line {line} out of range"
    got = lines[line - 1]
    token = snippet[:24] if snippet else ""
    if token and token not in got:
        return False, f"{rel}:{line} snippet-miss"
    return True, f"{rel}:{line}"


def main() -> int:
    fx = json.loads(EXAMPLES.read_text(encoding="utf-8"))
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))

    parse_ok = 0
    for ex in fx["required_six"]:
        r = S.check(ex["surface"], metrics)
        print(f"recount {ex['id']} code={r.code}")
        if r.code == "OK":
            parse_ok += 1

    bad = S.check(fx["planted_bad_unsat"]["surface"], metrics)
    taut = S.check(fx["planted_bad_tautology"]["surface"], metrics)
    unbound = S.check(fx["planted_bad_unbound"]["surface"], metrics)
    good = S.check(fx["known_good"]["surface"], metrics)
    fired = bad.code == "UNSATISFIABLE"
    silent = good.code == "OK"
    print(f"both-states planted-bad code={bad.code} fires={fired}")
    print(f"both-states known-good code={good.code} silent={silent}")
    print(f"negative-control rejects {fx['planted_bad_unsat']['surface']!r} with {bad.code}")
    print(f"tautology code={taut.code} unbound code={unbound.code}")
    if not (fired and silent):
        print("FAILED:CNL-0010-probe2 both-states did not discriminate")
        return 1
    if taut.code != "TAUTOLOGY" or unbound.code != "UNBOUND":
        print("FAILED:CNL-0010-probe2 tautology/unbound not independently rejected")
        return 1

    census = V.census(fx["required_six"])
    in_yes = census["counts"]["in_tree_expressible"]
    in_no = census["counts"]["in_tree_inexpressible"]
    v1_store = census["counts"]["v1_store_expressible"]
    v1_struct = census["counts"]["v1_structurally_expressible"]
    print(
        f"cited_v1={census['v1']['verdict']} v1_store={v1_store} v1_structural={v1_struct} "
        f"in_tree_expressible={in_yes} in_tree_inexpressible={in_no} "
        f"v1_silent_on_unsat={census['v1_string_silent_on_unsat']}"
    )
    if in_yes != 0 or in_no != 6:
        print("FAILED:CNL-0010-probe2 in-tree expressibility recount is not 0/6")
        return 1
    if v1_store != 6 or v1_struct != 0:
        print("FAILED:CNL-0010-probe2 v1 store/structural recount is not 6/0")
        return 1
    if census["v1"]["verdict"] != "ABSENT":
        print("FAILED:CNL-0010-probe2 cited 11-COUNCIL-SPECIFICATION.schema.json is not ABSENT")
        return 1
    if census["v1_string_silent_on_unsat"] is not True:
        print("FAILED:CNL-0010-probe2 reconstructed v1 string schema must accept x AND NOT x")
        return 1
    recon = census["v1_reconstructed_from_cnl0001"]
    if not recon.get("v1_stopping_expr_is_string"):
        print("FAILED:CNL-0010-probe2 CNL-0001 reconstruction is not a string stopping_expr")
        return 1

    if not OUT.is_file():
        print("FAILED:CNL-0010-probe2 artifact missing")
        return 1
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    rec = doc.get("x-cnl-0010") or {}
    claimed = rec.get("counts") or {}
    if claimed.get("required_six_parsed_ok") != parse_ok:
        print(
            f"FAILED:CNL-0010-probe2 recount disagreement parse_ok live={parse_ok} "
            f"claimed={claimed.get('required_six_parsed_ok')}"
        )
        return 1
    if claimed.get("in_tree_expressible") != in_yes:
        print("FAILED:CNL-0010-probe2 recount disagreement in_tree_expressible")
        return 1
    if claimed.get("in_tree_inexpressible") != in_no:
        print("FAILED:CNL-0010-probe2 recount disagreement in_tree_inexpressible")
        return 1
    if claimed.get("v1_store_expressible") != v1_store:
        print("FAILED:CNL-0010-probe2 recount disagreement v1_store_expressible")
        return 1
    if claimed.get("v1_structurally_expressible") != v1_struct:
        print("FAILED:CNL-0010-probe2 recount disagreement v1_structurally_expressible")
        return 1

    both = rec.get("both_states") or {}
    if not both.get("planted_bad", {}).get("fires") or not both.get("known_good", {}).get("silent"):
        print("FAILED:CNL-0010-probe2 artifact both_states flags disagree with live run")
        return 1

    for i, ev in enumerate(rec.get("evidence") or []):
        ok, why = resolve_anchor(str(ev.get("path") or ""), int(ev.get("line") or 0), str(ev.get("snippet") or ""))
        print(f"anchor[{i}] ok={ok} {why}")
        if not ok:
            print("FAILED:CNL-0010-probe2 unresolved evidence anchor")
            return 1

    # Mutant: dropping the unsat reject from the artifact's both_states must be visible.
    if str(both.get("planted_bad", {}).get("code") or "") != "UNSATISFIABLE":
        print("FAILED:CNL-0010-probe2 artifact did not record UNSATISFIABLE")
        return 1

    print(
        f"independent_recount parse_ok={parse_ok} unsat={bad.code} in_tree={in_yes}/{in_no}"
    )
    print("SUCCESS:CNL-0010-probe2 both-states negative-control independent-recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
