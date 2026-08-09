"""Executable gate for council protocol blueprints P37-P48.

Six checks, each with its own negative control. A detector unproven against a
known-broken state measures nothing, so nothing here reports a pass without also
demonstrating that it can fail.

  1. COUNT      - exactly 12 files on disk, read back, unique council_ids.
  2. VALIDATE   - every file through the reference validator (schema + semantics).
  3. MUTATE     - 4 mutations per file that MUST be rejected (SEM-001 drift,
                  SEM-004 roster/count mismatch, SEM-006 unknown participant,
                  schema unknown-key). 48 negative controls.
  4. EXECUTE    - every stopping expression evaluated in BOTH states: a snapshot
                  found by exhaustive search that satisfies it, and one that does
                  not. Snapshots are searched, not asserted.
  5. REQUIRE    - the twelve mandated content requirements, each with a mutation
                  proving the requirement check itself fires.
  6. COVER      - report topology / voting / speaking-order / stage-kind coverage.

Usage:
    python platform/council/_validate_protocols.py [--json OUT.json]
Terminal state (AGENTS.md Sec.4): last line is SUCCESS:<id> or FAILED:<id> <reason>.
"""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import os
import sys
from typing import Any, Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
PLATFORM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLATFORM, "lib"))

from councilspec.expression import evaluate, iter_leaves, parse, unparse  # noqa: E402
from councilspec.registry import CUSTOM_PREFIX, domain_of, enum_tokens  # noqa: E402
from councilspec.validate import validate_spec  # noqa: E402

PROTOCOLS = os.path.join(HERE, "protocols")
EXPECTED = 12
COMBINATORS = ("all_of", "any_of", "not", "weighted")


# ------------------------------------------------------------------------ loading


def load_protocols() -> Tuple[List[Tuple[str, Dict[str, Any]]], List[str]]:
    """Read THIS LANE's protocols back OFF DISK.

    Distinct from wfdsl.schemas.load_all, which loads the Workflow-DSL schema set.

    platform/council/protocols/ is SHARED: sibling lanes write P01-P36 into it
    concurrently (and use an uppercase `P` prefix where this lane used lowercase).
    Scoping to p37-p48 is deliberate - grading a sibling lane's design choices with
    this lane's requirement gate would report failures that are not ours to assert.
    """
    mine, others = [], []
    for name in sorted(os.listdir(PROTOCOLS)):
        if not name.endswith(".councilspec.json"):
            continue
        stem = name.lower()
        if any(stem.startswith(f"p{n}-") for n in range(37, 49)):
            with open(os.path.join(PROTOCOLS, name), "r", encoding="utf-8") as fh:
                mine.append((name, json.load(fh)))
        else:
            others.append(name)
    return mine, others


# --------------------------------------------------------------- 4. both-states exec


def _candidates(tree: Dict[str, Any]) -> Dict[str, List[Any]]:
    """Candidate snapshot values per metric, derived from the leaves themselves."""
    cand: Dict[str, set] = {}
    for leaf in iter_leaves(tree):
        metric, value = leaf["metric"], leaf["value"]
        domain = "custom" if metric.startswith(CUSTOM_PREFIX) else domain_of(metric)
        pool = cand.setdefault(metric, set())
        if domain == "boolean" or (domain == "custom" and isinstance(value, bool)):
            pool.update([True, False])
        elif domain == "enum" or (domain == "custom" and isinstance(value, str)):
            pool.add(value)
            pool.update(t for t in ("FAIL", "NO_DECISION") if t in enum_tokens())
        else:
            pool.update([0, value])
            pool.add(value + 1 if isinstance(value, int) else round(value + 0.1, 4))
            pool.add(value - 1 if isinstance(value, int) else round(value - 0.1, 4))
    return {k: sorted(v, key=repr) for k, v in cand.items()}


def both_states(
    tree: Dict[str, Any],
) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
    cand = _candidates(tree)
    metrics = sorted(cand)
    sat = unsat = None
    for combo in itertools.product(*(cand[m] for m in metrics)):
        snap = dict(zip(metrics, combo))
        if evaluate(tree, snap):
            if sat is None:
                sat = snap
        elif unsat is None:
            unsat = snap
        if sat is not None and unsat is not None:
            break
    return sat, unsat


# ------------------------------------------------------------------- 5. requirements


def _stage_kinds(spec: Dict[str, Any]) -> List[str]:
    return [s.get("kind") for s in spec.get("protocol", {}).get("sequence", [])]


def _stage_custom_names(spec: Dict[str, Any]) -> List[str]:
    return [
        s.get("custom_name")
        for s in spec.get("protocol", {}).get("sequence", [])
        if s.get("custom_name")
    ]


def requirements(spec: Dict[str, Any]) -> Dict[str, bool]:
    proto = spec.get("protocol") or {}
    obl = proto.get("obligations") or {}
    rounds = proto.get("rounds") or {}
    anti = spec.get("anti_failure") or {}
    stopping = spec.get("stopping") or {}
    tree = stopping.get("expression") or {}
    kinds = set(_stage_kinds(spec))

    adversarial_declared = sum(
        [
            bool(obl.get("cross_examination")) or "cross_examination" in kinds,
            bool(obl.get("rebuttal_required")),
            bool(obl.get("steelman_before_rebuttal"))
            or "steelman_before_rebuttal" in kinds,
        ]
    )
    quota_stages = [s for s in proto.get("sequence", []) if s.get("quotas")]
    dedup = (spec.get("targets") or {}).get("dedup") or {}

    return {
        "R01_topology": bool((spec.get("topology") or {}).get("kind")),
        "R02_speaking_order": bool(proto.get("speaking_order")),
        "R03_rounds": rounds.get("min") is not None and rounds.get("max") is not None,
        "R04_response_obligations": sum(1 for v in obl.values() if v is True) >= 3,
        "R05_crossexam_rebuttal_steelman": adversarial_declared >= 2,
        "R06_idea_novelty_quotas": bool(quota_stages)
        and bool(dedup.get("trivial_variant_policy")),
        "R07_voting_method": bool((spec.get("voting") or {}).get("method")),
        "R08_composable_stopping": any(k in tree for k in COMBINATORS),
        "R09_three_anti_failure_controls": len(anti.get("controls") or []) >= 3,
        "R10_fast_unanimity_response": bool(anti.get("fast_unanimity_response"))
        and (spec.get("consensus") or {}).get("fast_unanimity_is_suspicious") is True,
        "R11_outputs": bool((spec.get("outputs") or {}).get("required")),
        "R12_design_citation": any(
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.md" in c
            for c in (spec.get("metadata") or {}).get("spec_citations") or []
        ),
    }


REQ_BREAKERS = {
    "R01_topology": lambda s: s["topology"].pop("kind", None),
    "R02_speaking_order": lambda s: s["protocol"].pop("speaking_order", None),
    "R03_rounds": lambda s: s["protocol"].pop("rounds", None),
    "R04_response_obligations": lambda s: s["protocol"].update({"obligations": {}}),
    "R05_crossexam_rebuttal_steelman": lambda s: (
        s["protocol"].update({"obligations": {}}),
        [
            st.update({"kind": "round_robin"})
            for st in s["protocol"]["sequence"]
            if st.get("kind") in ("cross_examination", "steelman_before_rebuttal")
        ],
    ),
    "R06_idea_novelty_quotas": lambda s: (
        [st.pop("quotas", None) for st in s["protocol"]["sequence"]],
        (s.get("targets") or {}).pop("dedup", None),
    ),
    "R07_voting_method": lambda s: s["voting"].pop("method", None),
    "R08_composable_stopping": lambda s: s["stopping"].update(
        {"expression": {"metric": "rounds_elapsed", "op": ">=", "value": 1}}
    ),
    "R09_three_anti_failure_controls": lambda s: s["anti_failure"].update(
        {"controls": ["silence"]}
    ),
    "R10_fast_unanimity_response": lambda s: s["anti_failure"].update(
        {"fast_unanimity_response": []}
    ),
    "R11_outputs": lambda s: s["outputs"].update({"required": []}),
    "R12_design_citation": lambda s: s["metadata"].update({"spec_citations": []}),
}


# ---------------------------------------------------------------------- 3. mutations


def mut_sem001(spec: Dict[str, Any]) -> None:
    # Every spec in this lane declares source_expression; a KeyError here is a real
    # regression (the SEM-001 round-trip proof would be silently skipped), not a
    # condition to tolerate.
    spec["stopping"]["source_expression"] += " AND confidence >= 0.99"


def mut_sem004(spec: Dict[str, Any]) -> None:
    spec["participants"]["count"]["exact_n"] = len(spec["participants"]["roster"]) + 1


def mut_sem006(spec: Dict[str, Any]) -> None:
    spec["protocol"]["sequence"][0]["participants"] = ["ghost-seat-does-not-exist"]


def mut_schema(spec: Dict[str, Any]) -> None:
    spec["not_a_real_councilspec_key"] = True


MUTATIONS = {
    "SEM-001 source_expression drift": mut_sem001,
    "SEM-004 roster/count mismatch": mut_sem004,
    "SEM-006 unknown participant_id": mut_sem006,
    "schema unknown top-level key": mut_schema,
}


# ---------------------------------------------------------------------------- main


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args(argv)

    report: Dict[str, Any] = {"protocols": {}, "failures": [], "coverage": {}}
    failures: List[str] = report["failures"]
    specs, others = load_protocols()
    report["sibling_lane_files_present"] = len(others)

    # ---- 1. COUNT
    print(
        f"[1] COUNT  p37-p48 files on disk in {PROTOCOLS}: {len(specs)} "
        f"(expected {EXPECTED}); sibling-lane files ignored: {len(others)}"
    )
    if len(specs) != EXPECTED:
        failures.append(f"count={len(specs)} expected {EXPECTED}")
    ids = [s.get("council_id") for _, s in specs]
    if len(set(ids)) != len(ids):
        failures.append(f"duplicate council_id: {ids}")
    print(f"    unique council_ids: {len(set(ids))}")

    cov = {
        "topology": {},
        "voting": {},
        "speaking_order": {},
        "stage_kinds": set(),
        "anti_failure_controls": set(),
    }

    for name, spec in specs:
        entry: Dict[str, Any] = {"file": name, "council_id": spec.get("council_id")}

        # ---- 2. VALIDATE (reference validator: schema + semantics)
        res = validate_spec(spec)
        entry["schema_ok"] = res["schema_ok"]
        entry["ok"] = res["ok"]
        entry["schema_errors"] = res["schema_errors"]
        entry["semantic_errors"] = res["semantic_errors"]
        entry["warnings"] = res["warnings"]
        if not res["ok"]:
            failures.append(
                f"{name}: INVALID -> "
                + " | ".join(res["schema_errors"] + res["semantic_errors"])
            )
        if res["warnings"]:
            failures.append(f"{name}: emitted warnings -> {res['warnings']}")

        # ---- 3. MUTATE (negative controls)
        caught = {}
        for label, breaker in MUTATIONS.items():
            clone = copy.deepcopy(spec)
            breaker(clone)
            mres = validate_spec(clone)
            caught[label] = not mres["ok"]
            if mres["ok"]:
                failures.append(f"{name}: MUTATION SURVIVED ({label})")
        entry["mutations_caught"] = caught

        # ---- 4. EXECUTE both states
        tree = spec["stopping"]["expression"]
        src = spec["stopping"].get("source_expression")
        entry["stopping_source"] = src
        entry["stopping_unparsed"] = unparse(tree)
        entry["roundtrip_ok"] = (
            bool(src) and parse(src) == tree and parse(unparse(tree)) == tree
        )
        if not entry["roundtrip_ok"]:
            failures.append(f"{name}: stopping expression does not round-trip")
        sat, unsat = both_states(tree)
        entry["snapshot_satisfying"] = sat
        entry["snapshot_not_satisfying"] = unsat
        entry["both_states_ok"] = sat is not None and unsat is not None
        if not entry["both_states_ok"]:
            failures.append(
                f"{name}: stopping expression is not both-states executable "
                f"(sat={sat is not None}, unsat={unsat is not None})"
            )

        # per-stage exit_when expressions must also execute in both states
        stage_states = {}
        for stage in spec["protocol"]["sequence"]:
            if not stage.get("exit_when"):
                continue
            s2, u2 = both_states(stage["exit_when"])
            ok = s2 is not None and u2 is not None
            stage_states[stage.get("stage_id")] = ok
            if not ok:
                failures.append(
                    f"{name}: stage {stage.get('stage_id')} exit_when not "
                    f"both-states executable"
                )
        entry["stage_exit_when_both_states"] = stage_states

        # ---- 5. REQUIRE + its own negative control
        reqs = requirements(spec)
        entry["requirements"] = reqs
        for key, ok in reqs.items():
            if not ok:
                failures.append(f"{name}: requirement {key} NOT satisfied")
        breaker_fires = {}
        for key, breaker in REQ_BREAKERS.items():
            clone = copy.deepcopy(spec)
            breaker(clone)
            fires = requirements(clone)[key] is False
            breaker_fires[key] = fires
            if not fires:
                failures.append(
                    f"{name}: requirement check {key} did NOT fire when broken "
                    "(the check measures nothing)"
                )
        entry["requirement_checks_fire_when_broken"] = breaker_fires

        # ---- 6. COVER
        cov["topology"].setdefault(spec["topology"]["kind"], []).append(
            spec["council_id"]
        )
        cov["voting"].setdefault(spec["voting"]["method"], []).append(
            spec["council_id"]
        )
        cov["speaking_order"].setdefault(spec["protocol"]["speaking_order"], []).append(
            spec["council_id"]
        )
        cov["stage_kinds"].update(k for k in _stage_kinds(spec) if k)
        cov["anti_failure_controls"].update(spec["anti_failure"]["controls"])
        entry["anti_failure_controls"] = spec["anti_failure"]["controls"]
        entry["fast_unanimity_response"] = spec["anti_failure"][
            "fast_unanimity_response"
        ]
        entry["custom_stage_names"] = _stage_custom_names(spec)
        entry["subcouncils"] = [
            sub["council_id"] for sub in (spec["topology"].get("subcouncils") or [])
        ]

        report["protocols"][spec.get("council_id")] = entry

        flag = "OK      " if res["ok"] else "REJECTED"
        print(f"[2] {flag} {name}")
        for msg in res["schema_errors"]:
            print(f"        schema   {msg}")
        for msg in res["semantic_errors"]:
            print(f"        semantic {msg}")
        for msg in res["warnings"]:
            print(f"        warn     {msg}")

    report["coverage"] = {
        "topology_kinds": {k: sorted(v) for k, v in sorted(cov["topology"].items())},
        "voting_methods": {k: sorted(v) for k, v in sorted(cov["voting"].items())},
        "speaking_orders": {
            k: sorted(v) for k, v in sorted(cov["speaking_order"].items())
        },
        "stage_kinds": sorted(cov["stage_kinds"]),
        "anti_failure_controls": sorted(cov["anti_failure_controls"]),
    }

    print(
        f"[3] MUTATE   {len(specs) * len(MUTATIONS)} negative controls, "
        f"survivors={sum(1 for f in failures if 'MUTATION SURVIVED' in f)}"
    )
    print(
        f"[4] EXECUTE  both-states on {len(specs)} council stopping rules + "
        f"{sum(len(e['stage_exit_when_both_states']) for e in report['protocols'].values())} "
        "stage exit_when rules"
    )
    print(
        f"[5] REQUIRE  {len(REQ_BREAKERS)} requirements x {len(specs)} files, each with a "
        "break-it control"
    )
    print(
        f"[6] COVER    topology={len(cov['topology'])}/11 kinds  "
        f"voting={len(cov['voting'])} methods  "
        f"speaking_order={len(cov['speaking_order'])}/7  "
        f"anti_failure_controls={len(cov['anti_failure_controls'])}/25"
    )

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=True, default=str)
            fh.write("\n")
        print(f"    report -> {args.json_out}")

    if failures:
        for f in failures:
            print(f"    FAIL {f}")
        print(f"FAILED:council-protocols-37-48 {len(failures)} failure(s)")
        return 1
    print(
        f"SUCCESS:council-protocols-37-48 {len(specs)}/12 valid, "
        f"{len(specs) * len(MUTATIONS)} mutations caught, "
        f"{len(specs) * len(REQ_BREAKERS)} requirement controls fired, 0 warnings"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
