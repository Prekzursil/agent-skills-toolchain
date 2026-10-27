"""Verification battery for council protocol blueprints P01-P12.

A green validator that has never gone red on these files measures nothing, so this probe runs
four independent checks and refuses to report success unless all four hold:

1. CONTROL          - all 12 files validate unmutated (schema + 12 semantic rules).
2. MUTATION BATTERY - 10 single mutations per protocol, each of which MUST be rejected, and
                      each semantic mutation must be caught by the rule it targets. A mutation
                      that survives is a hole in the contract, not a pass.
3. BOTH STATES      - every stopping expression (and every stage exit_when) is executed against
                      a synthesized satisfying snapshot (expect True) and an all-violated
                      snapshot (expect False), plus a PER-CONJUNCT sensitivity sweep: flipping
                      any single conjunct of the closing rule must flip the verdict to False.
                      A conjunct that cannot change the outcome is decoration.
4. BRIEF FLOORS     - the unit brief's own requirements, counted mechanically: topology,
                      speaking order, rounds, response obligations, cross-examination /
                      rebuttal / steelman rules, idea and novelty quotas, voting method, a
                      composable stopping expression, >= 3 defended failure modes drawn from the
                      brief's OWN 14-item list (the schema enum is wider, so counting enum
                      members would over-report), and a fast-unanimity response drawn from the
                      brief's five concrete options.
                      Cross-cutting: an absent obligation key and a key set to false are
                      different claims, so presence and truthiness are measured separately.

Emits protocols/PROTOCOLS-01-12-VALIDATION.json.

Run:  python platform/council/_probe_p01_p12_verify.py
"""

from __future__ import annotations

import copy
import glob
import json
import os
import sys
from typing import Any, Callable, Dict, List, Mapping, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(HERE, "protocols")
STATUS = os.path.join(OUT_DIR, "PROTOCOLS-01-12-VALIDATION.json")

sys.path.insert(0, os.path.join(REPO, "platform", "lib"))

from councilspec.expression import evaluate, iter_leaves, unparse  # noqa: E402
from councilspec.semantics import check, errors  # noqa: E402
from councilspec.validate import schema_errors  # noqa: E402

IDS = [
    "p01-free-form-moderated-panel",
    "p02-round-robin",
    "p03-fishbowl",
    "p04-consensus-conference",
    "p05-rotating-chair",
    "p06-nominal-group-technique",
    "p07-oxford-debate",
    "p08-red-blue-team",
    "p09-dialectical-inquiry",
    "p10-mandated-devils-advocate",
    "p11-team-b-competitive-estimate",
    "p12-adversarial-collaboration",
]

XEXAM_STAGES = {
    "cross_examination",
    "steelman_before_rebuttal",
    "oxford",
    "socratic",
    "war_game",
}
IDEA_STAGES = {"brainstorm", "nominal_group", "six_hats"}

# The unit brief names 14 failure modes and requires each protocol to defend against >= 3 OF
# THEM. The schema enum is wider (it also offers instant_unanimity, moderator_capture,
# collusion, ...), so counting enum members would over-report compliance. This is the brief's
# list, mapped onto the enum spelling.
BRIEF_FAILURE_MODES = {
    "echo_chamber",
    "sycophancy",
    "participant_dominance",
    "silence",
    "circular_debate",
    "role_collapse",
    "missing_expertise",
    "strategic_voting",
    "evidence_free_majority",
    "premature_convergence",
    "endless_debate",
    "idea_count_gaming",
    "lost_dissent",
    "weak_synthesis",
}

# The brief also enumerates what a suspiciously fast unanimity must trigger.
BRIEF_FAST_UNANIMITY = {
    "blind_re_evaluation",
    "forced_dissent",
    "strongest_counterexample",
    "role_rotation",
    "recruit_independent_critic",
}


# ------------------------------------------------------------------ snapshot synthesis


def _step(value: Any) -> float:
    return 1 if float(value).is_integer() else 0.05


def _satisfy(leaf: Mapping[str, Any]) -> Any:
    op, val = leaf["op"], leaf["value"]
    if isinstance(val, bool):
        return val if op == "==" else (not val)
    if isinstance(val, str):
        return val if op == "==" else val + "-other"
    d = _step(val)
    return {">=": val, ">": val + d, "<=": val, "<": val - d, "==": val, "!=": val + d}[
        op
    ]


def _violate(leaf: Mapping[str, Any]) -> Any:
    op, val = leaf["op"], leaf["value"]
    if isinstance(val, bool):
        return (not val) if op == "==" else val
    if isinstance(val, str):
        return val + "-violated" if op == "==" else val
    d = _step(val)
    return {">=": val - d, ">": val, "<=": val + d, "<": val, "==": val + d, "!=": val}[
        op
    ]


def _chosen_leaves(node: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    """Leaves on ONE satisfying path: all_of takes every child, any_of takes the first."""
    if "all_of" in node:
        out: List[Mapping[str, Any]] = []
        for child in node["all_of"]:
            out += _chosen_leaves(child)
        return out
    if "any_of" in node:
        return _chosen_leaves(node["any_of"][0])
    if "not" in node or "weighted" in node:
        raise NotImplementedError(
            "no P01-P12 protocol uses NOT or WEIGHTED; extend if one does"
        )
    return [node]


def _snapshots(
    tree: Mapping[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """(satisfying snapshot, all-violated snapshot, chosen metric names)."""
    chosen = _chosen_leaves(tree)
    chosen_names = [lf["metric"] for lf in chosen]
    all_leaves = list(iter_leaves(tree))
    # Split by IDENTITY, not by metric name. Filtering `others` on "metric not in chosen_names"
    # makes the overlap set empty by construction and the guard below dead code - the sweep
    # would then silently be unsound for any metric that spans an any_of boundary.
    chosen_ids = {id(lf) for lf in chosen}
    others = [lf for lf in all_leaves if id(lf) not in chosen_ids]

    overlap = set(chosen_names) & {lf["metric"] for lf in others}
    if overlap:
        raise AssertionError(
            f"metric appears on and off the chosen path: {sorted(overlap)}"
        )

    # A metric constrained twice on the SAME path makes both the snapshot and the per-conjunct
    # sweep order-dependent: a dict comprehension keeps the last leaf's value, so `x>=3 AND x>=9`
    # happens to be satisfiable while `x>=9 AND x>=3` is not. Rather than depend on that luck,
    # reject the shape outright - it is also a design smell in a closing rule.
    dupes = sorted({m for m in chosen_names if chosen_names.count(m) > 1})
    if dupes:
        raise AssertionError(
            f"metric constrained more than once on the closing path: {dupes}"
        )

    sat = {lf["metric"]: _satisfy(lf) for lf in chosen}
    sat.update({lf["metric"]: _violate(lf) for lf in others})
    vio = {lf["metric"]: _violate(lf) for lf in all_leaves}
    return sat, vio, chosen_names


def _both_states(tree: Mapping[str, Any], label: str) -> Dict[str, Any]:
    sat, vio, chosen = _snapshots(tree)
    row: Dict[str, Any] = {
        "label": label,
        "expression": unparse(tree),
        "satisfied_snapshot_result": evaluate(tree, sat),
        "all_violated_snapshot_result": evaluate(tree, vio),
        "conjuncts_on_closing_path": chosen,
        "load_bearing_conjuncts": [],
        "decorative_conjuncts": [],
    }
    for metric in chosen:
        flipped = dict(sat)
        leaf = next(lf for lf in _chosen_leaves(tree) if lf["metric"] == metric)
        flipped[metric] = _violate(leaf)
        if evaluate(tree, flipped) is False:
            row["load_bearing_conjuncts"].append(metric)
        else:
            row["decorative_conjuncts"].append(metric)
    return row


# --------------------------------------------------------------------- mutation battery


def _first_roster_id(spec: Mapping[str, Any]) -> str:
    return spec["participants"]["roster"][0]["participant_id"]


def _mutations(
    spec: Dict[str, Any],
) -> List[Tuple[str, str, Callable[[Dict[str, Any]], bool]]]:
    """(mutation id, expected layer, apply-fn returning False when not applicable)."""

    def m_wrong_source(s: Dict[str, Any]) -> bool:
        s["stopping"]["source_expression"] = "consensus >= 0.01"
        return True

    def m_exact_n(s: Dict[str, Any]) -> bool:
        s["participants"]["count"]["exact_n"] += 1
        s["participants"]["count"]["max"] = s["participants"]["count"]["exact_n"]
        return True

    def m_dup_id(s: Dict[str, Any]) -> bool:
        roster = s["participants"]["roster"]
        roster[1]["participant_id"] = roster[0]["participant_id"]
        return True

    def m_unknown_ref(s: Dict[str, Any]) -> bool:
        old = _first_roster_id(s)
        s["participants"]["roster"][0]["participant_id"] = old + "-renamed"
        refs = (
            json.dumps(s["topology"])
            + json.dumps(s["voting"])
            + json.dumps(s["protocol"])
        )
        return f'"{old}"' in refs

    def m_cap_below_min(s: Dict[str, Any]) -> bool:
        s["stopping"]["hard_caps"]["max_rounds"] = 1
        s["protocol"]["rounds"]["min"] = 3
        return True

    def m_drop_minority(s: Dict[str, Any]) -> bool:
        if s["consensus"].get("minority_report") != "required":
            return False
        s["outcomes"]["allowed"] = [
            o for o in s["outcomes"]["allowed"] if o != "minority_report"
        ]
        return True

    def m_unknown_key(s: Dict[str, Any]) -> bool:
        s["surprise_field"] = "not in the contract"
        return True

    def m_bad_metric(s: Dict[str, Any]) -> bool:
        node = s["stopping"]["expression"]
        leaf = next(iter(iter_leaves(node)))
        leaf["metric"] = "vibes_score"
        return True

    def m_supermajority_no_threshold(s: Dict[str, Any]) -> bool:
        s["voting"]["method"] = "supermajority"
        s["voting"].pop("supermajority_threshold", None)
        return True

    def m_count_inverted(s: Dict[str, Any]) -> bool:
        s["participants"]["count"]["min"] = 99
        s["participants"]["count"]["max"] = 2
        return True

    return [
        ("source_expression-drift", "SEM-001", m_wrong_source),
        ("count-exact_n-vs-roster", "SEM-004", m_exact_n),
        ("duplicate-participant_id", "SEM-003", m_dup_id),
        ("dangling-participant-reference", "SEM-006", m_unknown_ref),
        ("round-cap-below-min", "SEM-011", m_cap_below_min),
        ("minority_report-required-but-not-allowed", "SEM-009", m_drop_minority),
        ("unknown-top-level-key", "schema", m_unknown_key),
        ("unregistered-stopping-metric", "schema", m_bad_metric),
        ("supermajority-without-threshold", "schema", m_supermajority_no_threshold),
        ("count-min-above-max", "SEM-002", m_count_inverted),
    ]


def _verdict(spec: Mapping[str, Any]) -> Tuple[List[str], List[str]]:
    serr = schema_errors(spec)
    sem = [str(f) for f in errors(check(spec))] if not serr else []
    return serr, sem


# ------------------------------------------------------------------------ brief floors


def _floors(spec: Mapping[str, Any]) -> Dict[str, Any]:
    proto = spec["protocol"]
    kinds = [st.get("kind") for st in proto["sequence"]]
    obligations = proto.get("obligations", {})
    quota_stages = [st for st in proto["sequence"] if st.get("quotas")]
    quota_keys = sorted({k for st in quota_stages for k in st["quotas"]})
    targets = spec.get("targets", {})
    anti = spec.get("anti_failure", {})
    # An ABSENT key and a key set to false are different claims. `obligations.get(k)` conflates
    # them, so "declared" is measured by key presence and "asserted" by truthiness, separately.
    xexam_keys = ("cross_examination", "rebuttal_required", "steelman_before_rebuttal")
    adversarial_mechanisms = sorted(set(kinds) & XEXAM_STAGES) + sorted(
        k for k in xexam_keys + ("forced_dissent",) if obligations.get(k)
    )
    return {
        "topology_kind": spec["topology"]["kind"],
        "speaking_order": proto.get("speaking_order"),
        "rounds": proto.get("rounds"),
        "obligations_declared": sorted(obligations),
        "obligations_asserted": sorted(k for k, v in obligations.items() if v),
        "xexam_rules_declared": sorted(k for k in xexam_keys if k in obligations),
        "xexam_rules_asserted": sorted(k for k in xexam_keys if obligations.get(k)),
        "critique_intensity": proto.get("critique_intensity"),
        "adversarial_mechanisms": adversarial_mechanisms,
        "quota_stages": len(quota_stages),
        "quota_keys": quota_keys,
        "novelty_controls": sorted(
            k
            for k in ("novelty_ratio", "diversity_index", "unique_ideas", "dedup")
            if k in targets
        ),
        "trivial_variant_policy": (targets.get("dedup") or {}).get(
            "trivial_variant_policy"
        ),
        "voting_method": spec["voting"]["method"],
        "stopping_is_composable": any(
            k in spec["stopping"]["expression"]
            for k in ("all_of", "any_of", "not", "weighted")
        ),
        "anti_failure_controls": len(anti.get("controls", [])),
        "controls_declared": sorted(anti.get("controls", [])),
        "controls_from_brief_list": sorted(
            set(anti.get("controls", [])) & BRIEF_FAILURE_MODES
        ),
        "controls_beyond_brief_list": sorted(
            set(anti.get("controls", [])) - BRIEF_FAILURE_MODES
        ),
        "fast_unanimity_response": anti.get("fast_unanimity_response", []),
        "fast_unanimity_is_suspicious": spec["consensus"].get(
            "fast_unanimity_is_suspicious"
        ),
    }


def _floor_failures(pid: str, f: Mapping[str, Any]) -> List[str]:
    out: List[str] = []
    if not f["topology_kind"]:
        out.append(f"{pid}: no topology kind")
    if not f["speaking_order"]:
        out.append(f"{pid}: no speaking order")
    if not (f["rounds"] or {}).get("max"):
        out.append(f"{pid}: no round cap")
    if len(f["obligations_declared"]) < 6:
        out.append(
            f"{pid}: only {len(f['obligations_declared'])} response obligations DECLARED"
        )
    if not f["obligations_asserted"]:
        out.append(f"{pid}: declares obligations but asserts none")
    if len(f["xexam_rules_declared"]) != 3:
        out.append(
            f"{pid}: cross-examination/rebuttal/steelman rules not all declared "
            f"(got {f['xexam_rules_declared']}); silence is not a rule"
        )
    if (
        f["critique_intensity"] in ("adversarial", "maximally_adversarial")
        and not f["adversarial_mechanisms"]
    ):
        out.append(
            f"{pid}: critique_intensity={f['critique_intensity']} but no adversarial stage or "
            f"obligation backs it"
        )
    if f["quota_stages"] < 1:
        out.append(f"{pid}: no stage declares idea/objection quotas")
    if len(f["novelty_controls"]) < 2 or f["trivial_variant_policy"] != "reject":
        out.append(
            f"{pid}: novelty/dedup controls missing or not rejecting trivial variants"
        )
    if not f["voting_method"]:
        out.append(f"{pid}: no voting method")
    if not f["stopping_is_composable"]:
        out.append(f"{pid}: stopping expression is a bare leaf, not composable")
    if f["anti_failure_controls"] < 3:
        out.append(f"{pid}: only {f['anti_failure_controls']} anti-failure controls")
    if len(f["controls_from_brief_list"]) < 3:
        out.append(
            f"{pid}: only {len(f['controls_from_brief_list'])} of the brief's 14 named failure "
            f"modes are defended ({f['controls_from_brief_list']}); enum members outside that "
            f"list do not satisfy the floor"
        )
    if not f["fast_unanimity_response"]:
        out.append(f"{pid}: fast unanimity triggers nothing")
    stray = sorted(set(f["fast_unanimity_response"]) - BRIEF_FAST_UNANIMITY)
    if stray:
        out.append(
            f"{pid}: fast-unanimity response is not one of the brief's options: {stray}"
        )
    if not f["fast_unanimity_is_suspicious"]:
        out.append(f"{pid}: fast unanimity is not flagged suspicious")
    return out


# ------------------------------------------------------------------------------- main


def _detector_controls(real: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Both-states control for THIS probe's own detectors.

    Every check above is only worth its verdict if it can go red. Each control below drives a
    known-BROKEN input through one detector and requires it to fire.
    """
    out: Dict[str, Any] = {}
    bad: List[str] = []

    # 1. floors detector: silent on the real spec, loud on a deliberately gutted copy.
    out["floors_on_real_spec"] = _floor_failures("control-real", _floors(real))
    if out["floors_on_real_spec"]:
        bad.append("floors detector fires on a known-GOOD spec")
    gutted = copy.deepcopy(real)
    gutted["protocol"]["obligations"] = {"must_cite_evidence": True}
    gutted["anti_failure"]["controls"] = gutted["anti_failure"]["controls"][:2]
    gutted["anti_failure"]["fast_unanimity_response"] = []
    gutted["consensus"]["fast_unanimity_is_suspicious"] = False
    gutted["targets"].pop("dedup", None)
    gutted["stopping"]["expression"] = {"metric": "consensus", "op": ">=", "value": 0.5}
    out["floors_on_gutted_spec"] = _floor_failures("control-gutted", _floors(gutted))
    if len(out["floors_on_gutted_spec"]) < 5:
        bad.append(
            f"floors detector too quiet on a gutted spec: {out['floors_on_gutted_spec']}"
        )

    # 2. snapshot overlap guard: must RAISE when one metric spans an any_of boundary.
    spanning = {
        "any_of": [
            {
                "all_of": [
                    {"metric": "consensus", "op": ">=", "value": 0.8},
                    {"metric": "rounds_elapsed", "op": ">=", "value": 3},
                ]
            },
            {"metric": "consensus", "op": ">=", "value": 0.1},
        ]
    }
    try:
        _snapshots(spanning)
        out["overlap_guard"] = "DID NOT FIRE"
        bad.append(
            "overlap guard is dead code: a metric spanning any_of was not caught"
        )
    except AssertionError as exc:
        out["overlap_guard"] = f"fired: {exc}"

    # 3. duplicate-metric guard: a metric constrained twice on one path makes the sweep
    #    order-dependent, so it must be REJECTED in both orderings, not accepted in the lucky one.
    for label, values in (("weak-then-strong", (3, 9)), ("strong-then-weak", (9, 3))):
        dup = {
            "all_of": [
                {"metric": "rounds_elapsed", "op": ">=", "value": values[0]},
                {"metric": "rounds_elapsed", "op": ">=", "value": values[1]},
            ]
        }
        try:
            _snapshots(dup)
            out[f"duplicate_metric_guard_{label}"] = "DID NOT FIRE"
            bad.append(f"duplicate-metric guard missed the {label} ordering")
        except AssertionError as exc:
            out[f"duplicate_metric_guard_{label}"] = f"fired: {exc}"

    # 4. mutation harness: a NO-OP mutation must be reported as SURVIVED, or the battery is
    #    incapable of reporting a survivor and its 117/117 means nothing.
    noop = copy.deepcopy(real)
    noop_serr, noop_sem = _verdict(noop)
    out["noop_mutation_reported_as"] = (
        "SURVIVED" if not (noop_serr or noop_sem) else "caught"
    )
    if out["noop_mutation_reported_as"] != "SURVIVED":
        bad.append("the mutation harness cannot report a survivor")

    return out, bad


def main() -> int:
    failures: List[str] = []
    rows: List[Dict[str, Any]] = []

    on_disk = sorted(
        os.path.basename(p)
        for p in glob.glob(os.path.join(OUT_DIR, "*.councilspec.json"))
    )
    mine = [f"{i}.councilspec.json" for i in IDS]
    missing = [m for m in mine if m not in on_disk]
    if missing:
        failures.append(f"missing protocol file(s): {missing}")

    for pid in IDS:
        path = os.path.join(OUT_DIR, f"{pid}.councilspec.json")
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            spec = json.load(fh)

        serr, sem = _verdict(spec)
        if serr or sem:
            failures.append(f"{pid}: CONTROL run is not clean: {serr[:3]}{sem[:3]}")

        # mutation battery
        muts: List[Dict[str, Any]] = []
        for mid, layer, apply in _mutations(spec):
            mutant = copy.deepcopy(spec)
            if not apply(mutant):
                muts.append({"mutation": mid, "expected_layer": layer, "result": "n/a"})
                continue
            m_serr, m_sem = _verdict(mutant)
            caught_by = (
                "schema"
                if m_serr
                else (sorted({s.split()[1] for s in m_sem})[0] if m_sem else None)
            )
            if caught_by is None:
                muts.append(
                    {"mutation": mid, "expected_layer": layer, "result": "SURVIVED"}
                )
                failures.append(
                    f"{pid}: mutation {mid} SURVIVED - the contract does not catch it"
                )
            elif layer != "schema" and layer not in {s.split()[1] for s in m_sem}:
                muts.append(
                    {
                        "mutation": mid,
                        "expected_layer": layer,
                        "result": "caught-by-wrong-layer",
                        "caught_by": caught_by,
                    }
                )
                failures.append(
                    f"{pid}: mutation {mid} expected {layer}, caught by {caught_by}"
                )
            else:
                muts.append(
                    {
                        "mutation": mid,
                        "expected_layer": layer,
                        "result": "caught",
                        "caught_by": caught_by,
                    }
                )

        # both-states execution, top-level rule and every stage exit_when
        states = [_both_states(spec["stopping"]["expression"], "stopping.expression")]
        for idx, stage in enumerate(spec["protocol"]["sequence"]):
            if isinstance(stage.get("exit_when"), Mapping):
                states.append(
                    _both_states(
                        stage["exit_when"],
                        f"protocol.sequence[{idx}].exit_when ({stage.get('stage_id')})",
                    )
                )
        for st in states:
            if st["satisfied_snapshot_result"] is not True:
                failures.append(
                    f"{pid}: {st['label']} did not fire on a satisfying snapshot"
                )
            if st["all_violated_snapshot_result"] is not False:
                failures.append(
                    f"{pid}: {st['label']} fired on an all-violated snapshot"
                )
            if st["decorative_conjuncts"]:
                failures.append(
                    f"{pid}: {st['label']} has conjuncts that cannot change the verdict: "
                    f"{st['decorative_conjuncts']}"
                )

        floors = _floors(spec)
        failures += _floor_failures(pid, floors)

        rows.append(
            {
                "protocol": pid,
                "file": f"{pid}.councilspec.json",
                "bytes": os.path.getsize(path),
                "schema": "PASS" if not serr else "FAIL",
                "semantic": "PASS" if not sem else "FAIL",
                "schema_errors": serr,
                "semantic_errors": sem,
                "warnings": [str(f) for f in check(spec) if f.severity == "WARN"],
                "source_expression_emitted": "source_expression" in spec["stopping"],
                "mutations": muts,
                "mutations_caught": sum(1 for m in muts if m["result"] == "caught"),
                "mutations_applicable": sum(1 for m in muts if m["result"] != "n/a"),
                "both_states": states,
                "floors": floors,
            }
        )

    controls: Dict[str, Any] = {"skipped": "no protocol loaded"}
    if rows:
        with open(os.path.join(OUT_DIR, rows[0]["file"]), "r", encoding="utf-8") as fh:
            controls, control_failures = _detector_controls(json.load(fh))
        failures += control_failures

    status = {
        "unit": "build/proto-1",
        "detector_controls": controls,
        "scope": "council protocol blueprints P01-P12 of 48 (DELIBERATIVE P01-P06, ADVERSARIAL P07-P12)",
        "schema": "platform/schema/councilspec.schema.json",
        "validator": "platform/lib/councilspec (jsonschema Draft202012 + 12 semantic rules)",
        "protocols_expected": len(IDS),
        "protocols_on_disk": len([r for r in rows if r["schema"] == "PASS"]),
        "all_councilspec_files_in_dir": len(on_disk),
        "mutations_applicable_total": sum(r["mutations_applicable"] for r in rows),
        "mutations_caught_total": sum(r["mutations_caught"] for r in rows),
        "mutations_survived_total": sum(
            1 for r in rows for m in r["mutations"] if m["result"] == "SURVIVED"
        ),
        "protocols": rows,
        "failures": failures,
        "verdict": "PASS" if not failures else "FAIL",
    }
    with open(STATUS, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(status, fh, indent=2)
        fh.write("\n")

    for r in rows:
        print(
            f"{r['schema']:4s}/{r['semantic']:4s}  {r['file']:<48s} "
            f"mut {r['mutations_caught']}/{r['mutations_applicable']} caught  "
            f"controls={r['floors']['anti_failure_controls']}  "
            f"conjuncts={len(r['both_states'][0]['load_bearing_conjuncts'])} load-bearing"
        )
    print(
        f"mutations: {status['mutations_caught_total']}/{status['mutations_applicable_total']} "
        f"caught, {status['mutations_survived_total']} survived"
    )
    if failures:
        for f in failures[:20]:
            print(f"  FAIL {f}")
        print(f"FAILED:verify-p01-p12 {len(failures)} failure(s); status -> {STATUS}")
        return 1
    print(
        f"SUCCESS:verify-p01-p12 12/12 clean, all mutations caught; status -> {STATUS}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
