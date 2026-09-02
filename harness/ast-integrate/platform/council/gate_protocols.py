"""Gate for council protocol blueprints P13-P24 (unit build/proto-2).

Six layers, every one executable. A protocol that fails any layer is NOT delivered.

  schema            - jsonschema Draft 2020-12 against councilspec.schema.json
  semantics         - SEM-001..SEM-012 from platform/lib/councilspec/semantics.py, and an
                      INDEPENDENT re-parse of source_expression (not trusting SEM-001 alone)
  declared_surfaces - topology, speaking order, rounds, response obligations,
                      cross-examination / rebuttal / steelman, voting method, receipt schema
  quotas            - idea/objection quotas on at least one stage plus a novelty-or-dedup
                      guard in targets (the anti idea-count-gaming surface)
  composite         - stopping.expression root is a boolean composite over >= 3 metrics
  anti_failure      - >= 3 mandated failure-class controls AND a concrete fast-unanimity trigger
  both_states       - every satisfying snapshot evaluates True, every not_satisfying snapshot
                      evaluates False (per-conjunct mutation battery on the stopping rule)
  anchors           - each metadata.spec_citations line actually lands on that protocol's
                      heading in the design doc

DETECTOR CONTROL (single-signal-verification rule 3b): `--mutations` proves the gate FIRES on
known-broken specs before its silence on the real ones is allowed to count as verification.

Run:  python platform/council/gate_protocols.py
      python platform/council/gate_protocols.py --mutations
      python platform/council/gate_protocols.py --json <out.json>
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "platform" / "lib"))

from councilspec.expression import ExpressionError, evaluate, iter_leaves, parse  # noqa: E402
from councilspec.validate import validate_spec  # noqa: E402

PROTO_DIR = REPO / "platform" / "council" / "protocols"
EXPECTATIONS_FILE = PROTO_DIR / "PROTOCOL-EXPECTATIONS.json"
DESIGN_DOC = (
    Path.home()
    / ".claude"
    / "harness-restore-20260806"
    / "12-COUNCIL-PROTOCOLS-AND-PRESETS.md"
)

EXPECTED_IDS = [f"P{n}" for n in range(13, 25)]

MANDATED_CONTROLS = frozenset(
    {
        "echo_chamber",
        "sycophancy",
        "moderator_capture",
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
)

CONCRETE_FAST_UNANIMITY = frozenset(
    {
        "blind_re_evaluation",
        "forced_dissent",
        "strongest_counterexample",
        "role_rotation",
        "recruit_independent_critic",
    }
)

OBLIGATION_KEYS = (
    "must_respond_to_prior",
    "must_cite_evidence",
    "cross_examination",
    "rebuttal_required",
    "steelman_before_rebuttal",
)

Failure = Tuple[str, str]  # (layer, message)


# --------------------------------------------------------------------------- layers


def check_schema_and_semantics(spec: Mapping[str, Any]) -> List[Failure]:
    out: List[Failure] = []
    res = validate_spec(spec)
    for msg in res["schema_errors"]:
        out.append(("schema", msg))
    for msg in res["semantic_errors"]:
        out.append(("semantics", msg))
    for msg in res["warnings"]:
        out.append(("semantics", f"WARN {msg}"))
    # Independent re-derivation: do not take SEM-001's word for it.
    stopping = spec.get("stopping") or {}
    src, tree = stopping.get("source_expression"), stopping.get("expression")
    if not src:
        out.append(
            (
                "semantics",
                "stopping.source_expression is absent; the human form is not pinned",
            )
        )
    else:
        try:
            if parse(src) != tree:
                out.append(
                    (
                        "semantics",
                        "independent re-parse: source_expression != expression",
                    )
                )
        except ExpressionError as exc:
            out.append(("semantics", f"independent re-parse failed: {exc}"))
    return out


def check_declared_surfaces(spec: Mapping[str, Any]) -> List[Failure]:
    out: List[Failure] = []
    proto = spec.get("protocol") or {}
    if not (spec.get("topology") or {}).get("kind"):
        out.append(("declared_surfaces", "topology.kind is not declared"))
    if not proto.get("speaking_order"):
        out.append(("declared_surfaces", "protocol.speaking_order is not declared"))
    rounds = proto.get("rounds") or {}
    if rounds.get("min") is None or rounds.get("max") is None:
        out.append(
            ("declared_surfaces", "protocol.rounds.min/max are not both declared")
        )
    obligations = proto.get("obligations") or {}
    missing = [k for k in OBLIGATION_KEYS if k not in obligations]
    if missing:
        out.append(
            (
                "declared_surfaces",
                f"protocol.obligations omits {missing}; silence is not a rule",
            )
        )
    engagement = [
        obligations.get(k)
        for k in ("cross_examination", "rebuttal_required", "steelman_before_rebuttal")
    ]
    if not any(engagement) and proto.get("critique_intensity") != "gentle":
        out.append(
            (
                "declared_surfaces",
                "no cross-examination, rebuttal or steelman obligation is true, and critique_intensity "
                "is not the declared no-critique value 'gentle'",
            )
        )
    if not (spec.get("voting") or {}).get("method"):
        out.append(("declared_surfaces", "voting.method is not declared"))
    if not (spec.get("outputs") or {}).get("receipt_schema"):
        out.append(("declared_surfaces", "outputs.receipt_schema is not declared"))
    if not (spec.get("stopping") or {}).get("hard_caps"):
        out.append(
            (
                "declared_surfaces",
                "stopping.hard_caps is not declared; the protocol cannot run forever",
            )
        )
    return out


def check_quotas(spec: Mapping[str, Any]) -> List[Failure]:
    out: List[Failure] = []
    stages = (spec.get("protocol") or {}).get("sequence") or []
    quota_stages = [s for s in stages if s.get("quotas")]
    if not quota_stages:
        out.append(
            (
                "quotas",
                "no stage declares quotas (ideas / novel ideas / objections / counterexamples)",
            )
        )
    targets = spec.get("targets") or {}
    dedup = targets.get("dedup") or {}
    guard = targets.get("novelty_ratio") is not None or dedup.get(
        "trivial_variant_policy"
    )
    if not guard:
        out.append(
            (
                "quotas",
                "targets declares neither novelty_ratio nor dedup.trivial_variant_policy, so a quota can "
                "be met with trivial variants",
            )
        )
    return out


def check_composite(spec: Mapping[str, Any]) -> List[Failure]:
    out: List[Failure] = []
    tree = (spec.get("stopping") or {}).get("expression") or {}
    if not any(k in tree for k in ("all_of", "any_of", "not", "weighted")):
        out.append(
            (
                "composite",
                "stopping.expression root is a bare leaf, not a composable boolean expression",
            )
        )
    metrics = {leaf["metric"] for leaf in iter_leaves(tree)} if tree else set()
    if len(metrics) < 3:
        out.append(
            (
                "composite",
                f"stopping.expression references only {len(metrics)} distinct metric(s); need >= 3",
            )
        )
    return out


def check_anti_failure(spec: Mapping[str, Any]) -> List[Failure]:
    out: List[Failure] = []
    af = spec.get("anti_failure") or {}
    controls = set(af.get("controls") or [])
    covered = sorted(controls & MANDATED_CONTROLS)
    if len(covered) < 3:
        out.append(
            (
                "anti_failure",
                f"declares only {len(covered)} mandated failure-class control(s) {covered}; at least 3 required",
            )
        )
    responses = af.get("fast_unanimity_response") or []
    if not responses:
        out.append(
            (
                "anti_failure",
                "fast_unanimity_response is empty: fast unanimity triggers nothing concrete",
            )
        )
    illegal = sorted(set(responses) - CONCRETE_FAST_UNANIMITY)
    if illegal:
        out.append(
            (
                "anti_failure",
                f"fast_unanimity_response contains non-concrete entries {illegal}",
            )
        )
    if (spec.get("consensus") or {}).get("fast_unanimity_is_suspicious") is not True:
        out.append(
            ("anti_failure", "consensus.fast_unanimity_is_suspicious is not true")
        )
    return out


def check_both_states(
    spec: Mapping[str, Any], expect: Mapping[str, Any]
) -> Tuple[List[Failure], int]:
    out: List[Failure] = []
    tree = (spec.get("stopping") or {}).get("expression") or {}
    checked = 0
    if not expect:
        return [
            ("both_states", "no both-states expectation declared for this protocol")
        ], 0
    for want, key in ((True, "satisfying"), (False, "not_satisfying")):
        snaps = expect.get(key) or []
        if not snaps:
            out.append(("both_states", f"no {key} snapshot declared"))
        for snap in snaps:
            checked += 1
            try:
                got = evaluate(tree, snap["metrics"])
            except Exception as exc:  # a missing metric is a real failure, not "false"
                out.append(
                    (
                        "both_states",
                        f"{key} [{snap.get('why')}] raised {type(exc).__name__}: {exc}",
                    )
                )
                continue
            if got is not want:
                out.append(
                    (
                        "both_states",
                        f"{key} [{snap.get('why')}] evaluated {got}, expected {want}",
                    )
                )
    if len(expect.get("not_satisfying") or []) < 2:
        out.append(
            (
                "both_states",
                "fewer than 2 not_satisfying snapshots: per-conjunct battery incomplete",
            )
        )
    return out, checked


_HEADING = re.compile(r"^#### (P\d\d) `([a-z0-9-]+)`")


def check_anchors(
    pid: str, spec: Mapping[str, Any], doc_lines: List[str] | None
) -> List[Failure]:
    out: List[Failure] = []
    cites = (spec.get("metadata") or {}).get("spec_citations") or []
    if not cites:
        return [("anchors", "metadata.spec_citations is empty")]
    if doc_lines is None:
        return [("anchors", f"NOT-CHECKED: design doc absent at {DESIGN_DOC}")]
    for cite in cites:
        _path, _, lines = cite.rpartition(":")
        start = int(lines.split("-")[0])
        if start < 1 or start > len(doc_lines):
            out.append(
                ("anchors", f"{cite} is outside the document (1..{len(doc_lines)})")
            )
            continue
        m = _HEADING.match(doc_lines[start - 1])
        if not m:
            out.append(
                (
                    "anchors",
                    f"{cite} does not land on a protocol heading; got {doc_lines[start - 1]!r}",
                )
            )
        elif m.group(1) != pid:
            out.append(("anchors", f"{cite} lands on {m.group(1)}, not {pid}"))
    return out


# --------------------------------------------------------------------------- driver


def check_one(
    pid: str, spec: Mapping[str, Any], expect: Mapping[str, Any], doc_lines
) -> Tuple[List[Failure], int]:
    failures: List[Failure] = []
    failures += check_schema_and_semantics(spec)
    failures += check_declared_surfaces(spec)
    failures += check_quotas(spec)
    failures += check_composite(spec)
    failures += check_anti_failure(spec)
    bs, checked = check_both_states(spec, expect)
    failures += bs
    failures += check_anchors(pid, spec, doc_lines)
    return failures, checked


def load() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any], List[str] | None]:
    manifest = json.loads(EXPECTATIONS_FILE.read_text(encoding="utf-8"))
    specs: Dict[str, Dict[str, Any]] = {}
    for entry in manifest["manifest"]:
        specs[entry["id"]] = json.loads(
            (PROTO_DIR / entry["file"]).read_text(encoding="utf-8")
        )
    doc_lines = (
        DESIGN_DOC.read_text(encoding="utf-8", errors="replace").splitlines()
        if DESIGN_DOC.is_file()
        else None
    )
    return specs, manifest, doc_lines


# --------------------------------------------------------------- mutation battery


def _mut_controls(spec, expect):
    spec["anti_failure"]["controls"] = ["prompt_injection"]


def _mut_bare_leaf(spec, expect):
    spec["stopping"]["source_expression"] = "rounds_elapsed >= 3"
    spec["stopping"]["expression"] = parse("rounds_elapsed >= 3")


def _mut_source_drift(spec, expect):
    spec["stopping"]["source_expression"] = "rounds_elapsed >= 99 OR consensus >= 0.5"


def _mut_no_fast_unanimity(spec, expect):
    spec["anti_failure"]["fast_unanimity_response"] = []


def _mut_unanimity_not_suspicious(spec, expect):
    spec["consensus"]["fast_unanimity_is_suspicious"] = False


def _mut_drop_speaking_order(spec, expect):
    spec["protocol"].pop("speaking_order", None)


def _mut_drop_obligation_key(spec, expect):
    spec["protocol"]["obligations"].pop("cross_examination", None)


def _mut_drop_quotas(spec, expect):
    for stage in spec["protocol"]["sequence"]:
        stage.pop("quotas", None)
    spec["targets"].pop("novelty_ratio", None)
    spec["targets"].pop("dedup", None)


def _mut_supermajority_no_threshold(spec, expect):
    spec["voting"]["method"] = "supermajority"
    spec["voting"].pop("supermajority_threshold", None)


def _mut_drop_receipt(spec, expect):
    spec["outputs"].pop("receipt_schema", None)


def _mut_flip_satisfying(spec, expect):
    # Corrupt the CONTROL, not the spec: a satisfying snapshot that no longer satisfies.
    expect["satisfying"][0]["metrics"] = {
        k: (
            0
            if isinstance(v, (int, float)) and not isinstance(v, bool)
            else (False if isinstance(v, bool) else "NOT_CHECKED")
        )
        for k, v in expect["satisfying"][0]["metrics"].items()
    }


def _mut_bad_anchor(spec, expect):
    spec["metadata"]["spec_citations"] = ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1"]


MUTATIONS: List[Tuple[str, str, Any]] = [
    ("M01 controls reduced to one non-mandated control", "anti_failure", _mut_controls),
    ("M02 stopping expression collapsed to a bare leaf", "composite", _mut_bare_leaf),
    ("M03 source_expression drifts from the tree", "semantics", _mut_source_drift),
    ("M04 fast_unanimity_response emptied", "anti_failure", _mut_no_fast_unanimity),
    (
        "M05 fast_unanimity_is_suspicious flipped false",
        "anti_failure",
        _mut_unanimity_not_suspicious,
    ),
    ("M06 speaking_order deleted", "declared_surfaces", _mut_drop_speaking_order),
    ("M07 an obligation key deleted", "declared_surfaces", _mut_drop_obligation_key),
    ("M08 all quotas and the novelty/dedup guard deleted", "quotas", _mut_drop_quotas),
    (
        "M09 supermajority without a threshold",
        "schema",
        _mut_supermajority_no_threshold,
    ),
    ("M10 receipt_schema deleted", "declared_surfaces", _mut_drop_receipt),
    (
        "M11 a satisfying both-states snapshot corrupted",
        "both_states",
        _mut_flip_satisfying,
    ),
    ("M12 spec_citation pointed at a non-heading line", "anchors", _mut_bad_anchor),
]


def run_mutations(specs, manifest, doc_lines) -> Tuple[bool, List[str]]:
    lines: List[str] = []
    ok = True
    base_id = (
        "P17"  # a protocol that exercises every layer: quotas, caps, unanimity, anchors
    )
    base_spec = specs[base_id]
    base_expect = manifest["expectations"][base_id]

    control_failures, _ = check_one(base_id, base_spec, base_expect, doc_lines)
    if control_failures:
        lines.append(
            f"[CONTROL] FAILED unmutated {base_id} already fails: {control_failures}"
        )
        return False, lines
    lines.append(f"[CONTROL] unmutated {base_id} passes all layers (0 failures)")

    for label, layer, mutate in MUTATIONS:
        spec = copy.deepcopy(base_spec)
        expect = copy.deepcopy(base_expect)
        mutate(spec, expect)
        failures, _ = check_one(base_id, spec, expect, doc_lines)
        layers = {lay for lay, _ in failures}
        if layer in layers:
            lines.append(f"[KILLED ] {label}  -> caught by {layer}")
        else:
            ok = False
            lines.append(
                f"[SURVIVED] {label}  -> expected layer {layer}, got {sorted(layers) or 'NOTHING'}"
            )
    return ok, lines


# --------------------------------------------------------------------------- main


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gate_protocols")
    ap.add_argument(
        "--mutations", action="store_true", help="run the detector control battery only"
    )
    ap.add_argument("--json", metavar="OUT", help="write a machine-readable report")
    args = ap.parse_args(argv)

    specs, manifest, doc_lines = load()

    if args.mutations:
        ok, lines = run_mutations(specs, manifest, doc_lines)
        for line in lines:
            print(line)
        killed = sum(1 for line in lines if line.startswith("[KILLED"))
        print(
            f"SUCCESS:protocol-gate-mutations {killed}/{len(MUTATIONS)} mutations caught by their declared layer"
            if ok
            else f"FAILED:protocol-gate-mutations {len(MUTATIONS) - killed} mutation(s) survived"
        )
        return 0 if ok else 1

    report: Dict[str, Any] = {
        "artifact": "platform/council/protocols/PROTOCOL-CONFORMANCE.json",
        "generated_by": "platform/council/gate_protocols.py --json",
        "unit": "build/proto-2",
        "lane": "PHASE 2C - COUNCIL PROTOCOL BLUEPRINTS 13-24 of 48 (design-doc ids P13..P24)",
        "schema_under_test": "platform/schema/councilspec.schema.json",
        "semantics_under_test": "platform/lib/councilspec/semantics.py (SEM-001..SEM-012)",
        "design_source": str(DESIGN_DOC),
        "honesty": (
            "Every value in this file was produced by running the gate over the on-disk JSON. "
            "Nothing here asserts that a council RAN: these are validated, executable "
            "specifications plus executed stopping-rule controls. Runtime producers named in "
            "stage exit_when clauses are NOT implemented by this unit and are NOT-CHECKED."
        ),
        "protocols": {},
        "gate_results": {},
        "totals": {},
    }
    all_failures: List[str] = []
    total_snapshots = 0

    missing = [pid for pid in EXPECTED_IDS if pid not in specs]
    extra = [pid for pid in specs if pid not in EXPECTED_IDS]
    if missing or extra:
        all_failures.append(f"count: missing={missing} unexpected={extra}")
    print(
        f"protocol files: {len(specs)} (expected {len(EXPECTED_IDS)}: {EXPECTED_IDS[0]}..{EXPECTED_IDS[-1]})"
    )

    for pid in EXPECTED_IDS:
        spec = specs.get(pid)
        if spec is None:
            print(f"  {pid}  MISSING")
            report["protocols"][pid] = {"status": "MISSING"}
            continue
        expect = manifest["expectations"].get(pid, {})
        failures, checked = check_one(pid, spec, expect, doc_lines)
        total_snapshots += checked
        status = "PASS" if not failures else "FAIL"
        tree = spec["stopping"]["expression"]
        report["protocols"][pid] = {
            "council_id": spec["council_id"],
            "title": spec["metadata"]["title"],
            "status": status,
            "topology": spec["topology"]["kind"],
            "speaking_order": spec["protocol"]["speaking_order"],
            "rounds": spec["protocol"]["rounds"],
            "voting_method": spec["voting"]["method"],
            "stopping_source": spec["stopping"]["source_expression"],
            "stopping_root": next(
                k
                for k in ("all_of", "any_of", "not", "weighted", "metric")
                if k in tree
            ),
            "metrics_referenced": sorted({lf["metric"] for lf in iter_leaves(tree)}),
            "mandated_controls": sorted(
                set(spec["anti_failure"]["controls"]) & MANDATED_CONTROLS
            ),
            "fast_unanimity_response": spec["anti_failure"]["fast_unanimity_response"],
            "both_states_snapshots": checked,
            "failures": [f"{lay}: {msg}" for lay, msg in failures],
        }
        controls = report["protocols"][pid]["mandated_controls"]
        print(
            f"  {pid}  {status}  {spec['council_id']:<34} topology={spec['topology']['kind']:<10} "
            f"vote={spec['voting']['method']:<20} controls={len(controls)} snapshots={checked}"
        )
        for lay, msg in failures:
            print(f"        {lay}: {msg}")
            all_failures.append(f"{pid} {lay}: {msg}")

    layers = (
        "schema",
        "semantics",
        "declared_surfaces",
        "quotas",
        "composite",
        "anti_failure",
        "both_states",
        "anchors",
    )
    for layer in layers:
        hits = [f for f in all_failures if f" {layer}: " in f]
        report["gate_results"][layer] = "PASS" if not hits else f"FAIL ({len(hits)})"
    report["gate_results"]["count_is_12"] = (
        "PASS" if len(specs) == 12 and not missing and not extra else "FAIL"
    )
    report["totals"] = {
        "protocols": len(specs),
        "both_states_snapshots": total_snapshots,
        "failures": len(all_failures),
        "design_doc_read": str(DESIGN_DOC) if doc_lines else "ABSENT",
    }

    print(f"\nboth-states snapshots evaluated: {total_snapshots}")
    for layer, verdict in report["gate_results"].items():
        print(f"  {layer:<18} {verdict}")

    if args.json:
        # The detector control belongs IN the record: a gate whose silence was never proved
        # against a known-broken state has measured nothing.
        mut_ok, mut_lines = run_mutations(specs, manifest, doc_lines)
        killed = sum(1 for line in mut_lines if line.startswith("[KILLED"))
        report["detector_control"] = {
            "base_protocol": "P17",
            "unmutated_control": "PASS"
            if "passes all layers" in mut_lines[0]
            else "FAIL",
            "mutations_declared": len(MUTATIONS),
            "mutations_killed": killed,
            "survivors": [line for line in mut_lines if line.startswith("[SURVIVED")],
            "verdict": "PASS" if mut_ok else "FAIL",
            "log": mut_lines,
        }
        siblings = sorted(
            p.name
            for p in PROTO_DIR.glob("*.councilspec.json")
            if not p.name.startswith(tuple(EXPECTED_IDS))
        )
        report["shared_directory"] = {
            "note": (
                "platform/council/protocols/ is shared with concurrent lanes. This lane owns exactly "
                "the 12 files whose names start P13..P24 and grades nothing else."
            ),
            "files_owned_by_this_lane": 12,
            "files_owned_by_sibling_lanes": len(siblings),
            "filename_convention_divergence": (
                "CROSS-LANE, REPORTED NOT FIXED: 36 of the 48 protocol files are named "
                "<council_id>.councilspec.json (lowercase 'p'), this lane's 12 are named "
                "P<NN>-<slug>.councilspec.json (uppercase 'P'). On Windows the difference is "
                "invisible; on a case-sensitive Linux runner a loader that rebuilds a path from "
                "council_id would miss these 12. Not renamed unilaterally because "
                "platform/council/PROTOCOLS-25-36-VALIDATION.json already records these exact "
                "uppercase names as foreign files, and platform/council/_validate_protocols.py "
                "already normalises with .lower(); a rename is a cross-lane call for the "
                "orchestrator, ideally in one commit that also refreshes that sibling record."
            ),
        }
        report["known_substrate_gaps"] = [
            "voting.method has no 'surprisingly_popular' value, which P24's design card names as its "
            "dependency; encoded as method=bayesian + belief_aggregation=bayesian_update + a "
            "custom:surprise_margin aggregation stage (see P24 metadata.notes).",
            "outcomes.allowed has no merits-free routing verdict, so P16's PROCEED / INSUFFICIENT / "
            "DISMISS output space is carried by a custom:threshold_verdict metric instead of an outcome.",
            "There is no registry metric for estimate spread, so P20/P21 carry the real Delphi "
            "stability criterion as stage-level custom metrics with declared producers.",
            "outputs.receipt_schema on all 12 files points at platform/schema/receipt.schema.json, "
            "which exists; the 674 catalog units that name command-center/schema/receipt.schema.json "
            "still cannot resolve it - that unresolved deploy mapping is a sibling lane's finding, "
            "inherited here and not fixed by this unit.",
        ]
        Path(args.json).write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"wrote {args.json}")
        print(
            f"detector control: {killed}/{len(MUTATIONS)} mutations killed, verdict={report['detector_control']['verdict']}"
        )
        if not mut_ok:
            all_failures.append("detector_control: a mutation survived")

    if all_failures:
        print(f"FAILED:protocol-gate {len(all_failures)} failure(s)")
        return 1
    print(
        f"SUCCESS:protocol-gate 12/12 protocols pass all {len(layers)} layers; {total_snapshots} snapshots evaluated"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
