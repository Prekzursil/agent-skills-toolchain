"""Two probes lane-2 must pass before its PASS results mean anything.

1. DETECTOR CONTROL (both-states). A validator that says OK for every one of my
   files proves nothing until it is shown to FIRE on a known-broken mutation of
   one of those same files. Six single-field mutations, each expected to be
   caught by a NAMED layer.

2. F-P2-01. The claim that `source_expression` cannot coexist with a custom
   metric that declares a `producer`, measured in both directions.

Also emits the cross-lane preset coverage matrix over the 24 spec-required
archetypes, read off whatever files actually exist in this directory.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "platform" / "lib"))

import jsonschema  # noqa: E402
from councilspec import semantics  # noqa: E402
from councilspec.expression import parse  # noqa: E402

SCHEMA = json.loads(
    (REPO / "platform" / "schema" / "councilspec.schema.json").read_text(
        encoding="utf-8"
    )
)
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)

REQUIRED_ARCHETYPES = SCHEMA["$defs"]["preset_name"]["enum"]


def judge(spec: Dict[str, Any]) -> Tuple[str, str]:
    """Return (layer, first message) or ("accepted", "")."""
    errs = sorted(VALIDATOR.iter_errors(spec), key=lambda e: list(e.absolute_path))
    if errs:
        return "schema", f"{list(errs[0].absolute_path)}: {errs[0].message[:120]}"
    sem = [f for f in semantics.check(spec) if f.severity == "ERROR"]
    if sem:
        return sem[0].rule, sem[0].message[:140]
    return "accepted", ""


# --------------------------------------------------------------- mutations
def m_bad_metric(s):
    s["stopping"]["expression"] = {"metric": "vibes", "op": ">=", "value": 1}
    s["stopping"].pop("source_expression", None)
    return s


def m_source_drift(s):
    s["stopping"]["source_expression"] = "consensus >= 0.99"
    return s


def m_roster_count_mismatch(s):
    s["participants"]["count"]["exact_n"] = 99
    s["participants"]["count"]["max"] = 99
    return s


def m_unknown_id(s):
    s["voting"].setdefault("veto", {})["holders"] = ["nobody-here"]
    s["voting"]["veto"].setdefault("scope", "safety_only")
    return s


def m_extra_key(s):
    s["surprise_field"] = True
    return s


def m_minority_report_uncovered(s):
    s.setdefault("consensus", {})["minority_report"] = "required"
    s["outcomes"]["allowed"] = [
        o for o in s["outcomes"]["allowed"] if o != "minority_report"
    ]
    return s


def m_cap_below_min(s):
    s["protocol"]["rounds"]["min"] = 9
    s["stopping"]["hard_caps"]["max_rounds"] = 2
    return s


MUTATIONS: List[Tuple[str, Callable, str]] = [
    ("unknown stopping metric", m_bad_metric, "schema"),
    ("source_expression drifts from tree", m_source_drift, "SEM-001"),
    ("roster length != count.exact_n", m_roster_count_mismatch, "SEM-004"),
    ("veto holder is not in the roster", m_unknown_id, "SEM-006"),
    ("unknown top-level key", m_extra_key, "schema"),
    (
        "minority_report required but not allowed",
        m_minority_report_uncovered,
        "SEM-009",
    ),
    ("hard cap below protocol.rounds.min", m_cap_below_min, "SEM-011"),
]

BASE = HERE / "c-s26-postmortem-5-blameless.councilspec.json"


def run_control() -> int:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    layer, msg = judge(base)
    print(f"[CONTROL] unmutated {BASE.name} -> {layer} {msg}")
    if layer != "accepted":
        print(
            "FAILED:detector-control the unmutated base does not pass; the probe measures nothing"
        )
        return 1
    bad = 0
    for name, mut, expect in MUTATIONS:
        got, msg = judge(mut(copy.deepcopy(base)))
        ok = got == expect
        bad += 0 if ok else 1
        print(
            f"  [{'ok  ' if ok else 'MISS'}] {name:<42} expected={expect:<8} got={got:<8} {msg}"
        )
    if bad:
        print(
            f"FAILED:detector-control {bad}/{len(MUTATIONS)} mutations were not caught by the "
            "declared layer"
        )
        return 1
    print(
        f"SUCCESS:detector-control {len(MUTATIONS)}/{len(MUTATIONS)} mutations caught by the "
        "declared layer; the validator fires on a known-broken state"
    )
    return 0


def run_fp201() -> int:
    """Both directions of the producer-vs-source_expression claim."""
    tree_with_producer = {
        "all_of": [
            {"metric": "counterexamples_found", "op": ">=", "value": 8},
            {
                "metric": "custom:attacks_mapped_to_real_incident",
                "op": ">=",
                "value": 1,
                "value_type": "number",
                "producer": "the owner representative",
            },
        ]
    }
    tree_without = copy.deepcopy(tree_with_producer)
    tree_without["all_of"][1].pop("producer")
    human = "counterexamples_found >= 8 AND custom:attacks_mapped_to_real_incident >= 1"
    parsed = parse(human)

    base = json.loads(
        (HERE / "c-s27-kill-the-company-5.councilspec.json").read_text(encoding="utf-8")
    )

    a = copy.deepcopy(base)
    a["stopping"]["expression"] = tree_with_producer
    a["stopping"]["source_expression"] = human
    la, ma = judge(a)

    b = copy.deepcopy(base)
    b["stopping"]["expression"] = tree_without
    b["stopping"]["source_expression"] = human
    lb, mb = judge(b)

    c = copy.deepcopy(base)
    c["stopping"]["expression"] = tree_with_producer
    c["stopping"].pop("source_expression", None)
    lc, mc = judge(c)
    warns_c = [f.rule for f in semantics.check(c) if f.severity == "WARN"]

    print(f"  A producer + source_expression -> {la}  {ma}")
    print(f"  B no producer + source_expression -> {lb}  {mb}")
    print(f"  C producer, no source_expression -> {lc} (warnings: {warns_c or 'none'})")
    print(f"  parse({human!r}) emits keys {sorted(parsed['all_of'][1])}")
    ok = (
        la == "SEM-001"
        and lb == "accepted"
        and lc == "accepted"
        and "SEM-012" not in warns_c
    )
    print(
        (
            "SUCCESS:F-P2-01 CONFIRMED - a producer-bearing custom leaf cannot carry a "
            "source_expression; dropping the producer restores it, keeping it costs nothing else"
        )
        if ok
        else "FAILED:F-P2-01 the claim did not reproduce as stated"
    )
    return 0 if ok else 1


def coverage() -> Dict[str, Any]:
    rows: Dict[str, List[str]] = {a: [] for a in REQUIRED_ARCHETYPES}
    files = sorted(HERE.glob("*.councilspec.json"))
    for f in files:
        spec = json.loads(f.read_text(encoding="utf-8"))
        label = spec.get("preset", "(none)")
        rows.setdefault(label, []).append(f.name)
    required = [a for a in REQUIRED_ARCHETYPES if a != "custom"]
    covered = [a for a in required if rows.get(a)]
    missing = [a for a in required if not rows.get(a)]
    dupes = {a: v for a, v in rows.items() if a != "custom" and len(v) > 1}
    print(f"\nfiles in directory: {len(files)}")
    print(f"required archetypes covered: {len(covered)}/{len(required)}")
    print(f"NOT YET COVERED by ANY file in this directory ({len(missing)}): {missing}")
    print(f"archetypes carried by >1 file: { {k: v for k, v in dupes.items()} }")
    return {
        "files": [f.name for f in files],
        "covered": covered,
        "missing": missing,
        "duplicates": dupes,
        "by_archetype": rows,
    }


def main() -> int:
    rc = run_control()
    print()
    rc |= run_fp201()
    cov = coverage()
    (HERE / "_lane2_probe_controls_out.json").write_text(
        json.dumps({"coverage": cov}, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
