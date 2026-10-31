#!/usr/bin/env python3
"""Named probe 1 (CNL-0078): the stopping expression replays executable.

Re-derives the stopping decision with an inline parser that never reads the
spec's own "fired" flags: parse verbatim_expression (two comparisons joined by
AND), evaluate both sides against the FIRE fixture's recorded values, and
require the replayed decision to match the recorded verdict. The spec's
independent recount (groupby-mechanism identity) must agree with the fixture
numbers.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
def _catalog_artifact() -> Path:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for u in cat.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UNIT:
            return REPO / str(u.get("output_path") or "").replace(chr(92), "/")
    raise RuntimeError(f"{UNIT} absent from catalog")


UNIT = "CNL-0078"
ART = _catalog_artifact()


def replay(expression: str, values: dict) -> bool:
    """Mechanically independent evaluation: regex-parse, compare, AND."""
    sides = [s.strip() for s in expression.split(" AND ")]
    if len(sides) != 2:
        raise ValueError(f"not a two-conjunct AND: {expression!r}")
    out = True
    for side in sides:
        m = re.fullmatch(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*(>=|<=|>|<|==)\s*([0-9.]+)\s*", side)
        if not m:
            raise ValueError(f"unparseable conjunct: {side!r}")
        name, op, num = m.group(1), m.group(2), float(m.group(3))
        if name not in values:
            raise KeyError(f"fixture lacks value for {name}")
        left = float(values[name])
        right = num
        conj = {"<=": left <= right, ">=": left >= right, "<": left < right, ">": left > right, "==": left == right}[op]
        out = out and conj
    return out


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print(f"FAILED:{UNIT}-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if f"SUCCESS:{UNIT}" not in text:
        print(f"FAILED:{UNIT}-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:{UNIT}-probe1 self-declared {st}")
        return 1
    rev = doc.get("reviewer") or {}
    if not (rev.get("verdict") == "PASS" and rev.get("independent") is True):
        print(f"FAILED:{UNIT}-probe1 reviewer closure absent")
        return 1

    expression = str(doc.get("verbatim_expression") or "")
    if expression != "unique_ideas >= 100 AND completeness_score >= 0.90":
        print(f"FAILED:{UNIT}-probe1 verbatim expression drifted: {expression!r}")
        return 1

    runs = doc.get("fixture_runs") or {}
    fire = runs.get("fire") or {}
    replay_fire = replay(expression, fire)
    if not replay_fire:
        print(f"FAILED:{UNIT}-probe1 replay does not FIRE on the fire fixture: {fire}")
        return 1
    if str(fire.get("verdict") or "").upper() != "FIRE" or fire.get("fired") is not True:
        print(f"FAILED:{UNIT}-probe1 recorded fire verdict mismatch")
        return 1

    recount = fire.get("independent_recount") or {}
    if not (
        recount.get("method")
        and float(recount.get("unique_ideas")) == float(fire.get("unique_ideas"))
        and float(recount.get("completeness_score")) == float(fire.get("completeness_score"))
    ):
        print(f"FAILED:{UNIT}-probe1 independent recount missing or disagrees")
        return 1

    bindings = doc.get("bindings") or {}
    if not bindings:
        print(f"FAILED:{UNIT}-probe1 bindings absent")
        return 1
    ui = str(fire.get("unique_identity") or "")
    ci = str(fire.get("completeness_identity") or "")
    if not ui or ui != ci:
        print(f"FAILED:{UNIT}-probe1 idea/scorer identity disagree (bound={fire.get('bound')})")
        return 1

    row = {
        "unit_id": UNIT,
        "probe": "probe1-stopping-expression-replay",
        "expression": expression,
        "replayed_fire": replay_fire,
        "recorded_verdict": fire.get("verdict"),
        "independent_recount_method": recount.get("method"),
        "recount_agrees": True,
        "identity_bound": ui,
        "n_raw": fire.get("n_raw"),
    }
    print(json.dumps(row, indent=1))
    print(f"SUCCESS:{UNIT}-probe1 stopping expression replays executable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
