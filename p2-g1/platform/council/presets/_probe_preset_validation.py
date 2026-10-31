"""Verification harness for council presets 33-48 (unit build/preset-3).

Six checks, all mechanical. Every one FAILS CLOSED - a missing input, an empty walk, or a
parse error returns non-zero rather than "found nothing, so pass".

  1. MANIFEST      - exactly the 16 expected design ids are on disk, no more, no fewer.
  2. BASELINE      - every file is OK under the real reference validator
                     (councilspec JSON Schema + all 12 semantic rules).
  3. MUTATIONS     - the both-states control. Each preset is mutated in up to 12 ways and every
                     applicable mutation MUST flip it to REJECTED. A validator that accepts a
                     mutant is not validating; a suite that never goes red measures nothing.
  4. DIAL POINTERS - every JSON Pointer named in a preset's metadata.notes "EDITABLE DIALS"
                     prose must actually resolve in that preset. This makes the editability
                     claim falsifiable instead of decorative.
  5. DOC CHANNELS  - every preset carries per-dial documentation (a `note` on each stop leaf, or
                     a declared source_expression) plus title/notes/citations/lineage.
  6. COVERAGE      - which of the spec's 24 required preset names this slice claims.

Writes LANE-3-PRESET-VALIDATION.json. Run from the repo root:
    python platform/council/presets/_probe_preset_validation.py
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
from typing import Any, Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "..", "lib"))
sys.path.insert(0, LIB)

from councilspec.expression import iter_leaves  # noqa: E402
from councilspec.validate import validate_spec  # noqa: E402

# Reuse the sibling Phase-4 contract's RFC 6901 resolver rather than writing a second one
# (platform/lib/wfdsl/capabilities.py:25). Two pointer resolvers that drift is exactly the
# "two implementations disagree" class this wave already hit on the gate-A predicate.
from wfdsl.capabilities import PointerError, resolve_pointer as _resolve  # noqa: E402

EXPECTED_IDS = [f"C-D{n}" for n in range(33, 46)] + ["C-X46", "C-X47", "C-X48"]

# The spec's required-preset list, _USER-PROMPTS.md:11200-11224.
REQUIRED_PRESETS = [
    "hundred_idea_brainstorm",
    "architecture_review_board",
    "scientific_peer_review",
    "code_review_tribunal",
    "security_red_blue_council",
    "incident_war_room",
    "root_cause_council",
    "product_strategy_council",
    "requirements_council",
    "plan_review_council",
    "release_readiness_board",
    "ethics_legal_board",
    "risk_committee",
    "roadmap_prioritization",
    "forecasting_council",
    "stakeholder_user_panel",
    "negotiation_council",
    "adversarial_collaboration",
    "evidence_adjudication_jury",
    "benchmark_results_jury",
    "innovation_moonshot_council",
    "postmortem_council",
    "standing_watch_council",
    "general_purpose_auto_composed",
]

# A JSON Pointer named in prose. `.` is deliberately EXCLUDED from the segment class: an earlier
# version allowed it and silently absorbed sentence-ending periods, producing 16 bogus
# "/budgets/time_minutes." pointers that then failed to resolve. Detector bug, not a data bug.
_POINTER_RE = re.compile(r"/[a-z_]+(?:/[a-z0-9_]+)+")


# ------------------------------------------------------------------ RFC 6901
def resolve_pointer(doc: Any, pointer: str) -> Tuple[bool, Any]:
    """Boolean-returning wrapper over the sibling contract's raising resolver."""
    try:
        return True, _resolve(doc, pointer)
    except PointerError:
        return False, None


# ---------------------------------------------------------------- mutations
def _leaves(spec):
    expr = spec.get("stopping", {}).get("expression")
    return list(iter_leaves(expr)) if isinstance(expr, dict) else []


def control_mutant(spec: Dict[str, Any]) -> Dict[str, Any]:
    """A benign edit that MUST still validate.

    Without this, a battery reporting "0 survivors" is silent in both states: the
    survivor-detection branch never runs, so nothing proves it could ever fire, and nothing
    proves the deepcopy-and-edit mechanism is not corrupting every mutant into a rejection
    (which would make all 131 "catches" meaningless). This control exercises the OK branch
    through exactly the same machinery.
    """
    m = copy.deepcopy(spec)
    m["metadata"]["title"] = m["metadata"]["title"] + " [benign control edit]"
    return m


def build_mutants(spec: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """Single-change mutants. Each must be REJECTED by the validator."""
    out: List[Tuple[str, Dict[str, Any]]] = []

    def add(name, fn):
        m = copy.deepcopy(spec)
        if fn(m) is not False:
            out.append((name, m))

    # universal - every preset must be killed by all four
    add(
        "M01-schema_version-major-2", lambda m: m.__setitem__("schema_version", "2.0.0")
    )
    add("M02-unknown-top-level-key", lambda m: m.__setitem__("surprise_field", True))
    add("M03-council_id-bad-pattern", lambda m: m.__setitem__("council_id", "BAD ID"))
    add(
        "M04-outcomes-allowed-empty",
        lambda m: (
            m["outcomes"].__setitem__("allowed", []) if "outcomes" in m else False
        ),
    )

    # conditional - only where the feature is present
    def drop_roster(m):
        if m["participants"].get("selection", {}).get("mode") != "exact" or not m[
            "participants"
        ].get("roster"):
            return False
        m["participants"].pop("roster")

    add("M05-exact-selection-without-roster(SEM-004)", drop_roster)

    def drop_minority(m):
        if m.get("consensus", {}).get(
            "minority_report"
        ) != "required" or "minority_report" not in m.get("outcomes", {}).get(
            "allowed", []
        ):
            return False
        m["outcomes"]["allowed"] = [
            o for o in m["outcomes"]["allowed"] if o != "minority_report"
        ]

    add("M06-required-minority-report-not-allowed(SEM-009)", drop_minority)

    def drop_impossibility(m):
        metrics = {lf["metric"] for lf in _leaves(m)}
        if (
            "proof_of_impossibility" not in metrics
            or "proof_of_impossibility" not in m.get("outcomes", {}).get("allowed", [])
        ):
            return False
        m["outcomes"]["allowed"] = [
            o for o in m["outcomes"]["allowed"] if o != "proof_of_impossibility"
        ]

    add("M07-impossibility-stop-without-outcome(SEM-009)", drop_impossibility)

    def dupe_id(m):
        roster = m["participants"].get("roster")
        if not roster or len(roster) < 2:
            return False
        roster[1]["participant_id"] = roster[0]["participant_id"]

    add("M08-duplicate-participant_id(SEM-003)", dupe_id)

    def drop_threshold(m):
        if m["voting"].get("method") != "supermajority":
            return False
        m["voting"].pop("supermajority_threshold", None)

    add("M09-supermajority-without-threshold", drop_threshold)

    def perturb_source(m):
        if not m.get("stopping", {}).get("source_expression"):
            return False
        for leaf in _leaves(m):
            if isinstance(leaf.get("value"), (int, float)) and not isinstance(
                leaf["value"], bool
            ):
                leaf["value"] = leaf["value"] + 1
                return None
        return False

    add("M10-source_expression-tree-drift(SEM-001)", perturb_source)

    def break_round_cap(m):
        caps = m.get("stopping", {}).get("hard_caps", {})
        rmin = m.get("protocol", {}).get("rounds", {}).get("min")
        if "max_rounds" not in caps or not rmin or rmin < 2:
            return False
        caps["max_rounds"] = rmin - 1

    add("M11-round-cap-below-rounds-min(SEM-011)", break_round_cap)

    def raise_idea_gate(m):
        target = m.get("targets", {}).get("unique_ideas")
        if target is None:
            return False
        hit = False
        for leaf in _leaves(m):
            if leaf["metric"] in ("unique_ideas", "novel_ideas", "deduplicated_ideas"):
                leaf["value"] = target + 1
                leaf.pop(
                    "note", None
                )  # keep source_expression specs from failing via SEM-001
                hit = True
        if not hit:
            return False
        m.get("stopping", {}).pop("source_expression", None)

    add("M12-idea-gate-above-target(SEM-007)", raise_idea_gate)

    def unknown_role(m):
        roster = m["participants"].get("roster")
        if not roster:
            return False
        roster[0]["role"] = "supreme_overlord"

    add("M13-role-outside-template-vocabulary", unknown_role)

    return out


def main() -> int:
    report: Dict[str, Any] = {"unit": "build/preset-3"}
    problems: List[str] = []

    # ---- 1. manifest
    all_on_disk = sorted(f for f in os.listdir(HERE) if f.endswith(".councilspec.json"))
    # This directory is SHARED with the other three preset lanes. Only files whose name starts
    # with one of THIS slice's design ids are ours to gate; a sibling lane's file is neither a
    # missing input nor an error here.
    by_id: Dict[str, List[str]] = {}
    for name in all_on_disk:
        m = re.match(r"^(C-[A-Z]\d+)-", name)
        if m and m.group(1) in EXPECTED_IDS:
            by_id.setdefault(m.group(1), []).append(name)
    mine = sorted(n for v in by_id.values() for n in v)
    co_located = [n for n in all_on_disk if n not in set(mine)]

    missing = [i for i in EXPECTED_IDS if i not in by_id]
    dupes = {i: v for i, v in by_id.items() if len(v) > 1}
    if not all_on_disk:
        problems.append(
            "no *.councilspec.json files found - empty walk, failing closed"
        )
    if missing:
        problems.append(f"missing design ids from this slice: {missing}")
    if dupes:
        problems.append(f"more than one file per design id: {dupes}")
    if len(mine) != len(EXPECTED_IDS):
        problems.append(
            f"this slice owns {len(mine)} files, expected {len(EXPECTED_IDS)}"
        )
    print(
        f"MANIFEST   mine={len(mine)}/{len(EXPECTED_IDS)} missing={len(missing)} "
        f"co-located-from-other-lanes={len(co_located)} (not gated here)"
    )

    # ---- 2/3/4/5 per file
    per_file: Dict[str, Any] = {}
    mut_total = mut_caught = 0
    controls_passed = [0]
    pointer_total = 0
    presets_claimed: Dict[str, List[str]] = {}
    lineage_refs: Dict[str, List[str]] = {}

    for design_id in EXPECTED_IDS:
        if design_id not in by_id:
            continue
        name = by_id[design_id][0]
        path = os.path.join(HERE, name)
        with open(path, "r", encoding="utf-8") as fh:
            spec = json.load(fh)

        base = validate_spec(spec)
        if not base["ok"]:
            problems.append(
                f"{name}: baseline REJECTED -> "
                f"{base['schema_errors'] + base['semantic_errors']}"
            )

        # mutation battery (both-states control)
        mutants = build_mutants(spec)
        survivors = []
        for mname, mutant in mutants:
            mut_total += 1
            if validate_spec(mutant)["ok"]:
                survivors.append(mname)
            else:
                mut_caught += 1
        if survivors:
            problems.append(
                f"{name}: mutants SURVIVED (validator did not catch): {survivors}"
            )

        # control: the benign edit must survive, proving the OK branch and the mutation
        # mechanism both work. If this is rejected, every "catch" above is suspect.
        control_ok = validate_spec(control_mutant(spec))["ok"]
        if not control_ok:
            problems.append(
                f"{name}: CONTROL FAILED - a benign edit was rejected, so the "
                "mutation battery's rejections prove nothing"
            )
        controls_passed[0] += int(control_ok)

        # dial pointers named in the prose
        notes = spec.get("metadata", {}).get("notes", "")
        pointers = sorted(set(_POINTER_RE.findall(notes)))
        unresolved = [p for p in pointers if not resolve_pointer(spec, p)[0]]
        pointer_total += len(pointers)
        if not pointers:
            problems.append(f"{name}: metadata.notes names no editable dial pointers")
        if unresolved:
            problems.append(f"{name}: dial pointers do not resolve: {unresolved}")

        # documentation channels
        leaves = _leaves(spec)
        noted = sum(1 for lf in leaves if lf.get("note"))
        has_src = bool(spec.get("stopping", {}).get("source_expression"))
        md = spec.get("metadata", {})
        if not leaves:
            problems.append(f"{name}: stopping expression has no leaves")
        if noted != len(leaves) and not has_src:
            problems.append(
                f"{name}: {len(leaves) - noted} stop leaf/leaves carry no `note` "
                "and no source_expression is declared"
            )
        for field in ("title", "notes", "spec_citations", "lineage"):
            if not md.get(field):
                problems.append(f"{name}: metadata.{field} is missing or empty")

        # Coverage counts the `preset` field ONLY. extends_preset is lineage ("forked from"),
        # not a claim to BE that preset - folding it in would overclaim coverage of a required
        # name that no file in this slice actually instantiates.
        if spec.get("preset"):
            presets_claimed.setdefault(spec["preset"], []).append(design_id)
        if spec.get("extends_preset"):
            lineage_refs.setdefault(spec["extends_preset"], []).append(design_id)

        per_file[design_id] = {
            "file": name,
            "council_id": spec.get("council_id"),
            "preset": spec.get("preset"),
            "extends_preset": spec.get("extends_preset"),
            "seats_declared": (
                spec.get("participants", {}).get("count", {}).get("exact_n")
                or spec.get("participants", {}).get("count", {}).get("max")
            ),
            "roster_entries": len(spec.get("participants", {}).get("roster") or []),
            "subcouncils": len(spec.get("topology", {}).get("subcouncils") or []),
            "validator": "OK" if base["ok"] else "REJECTED",
            "warnings": base["warnings"],
            "stop_leaves": len(leaves),
            "stop_leaves_with_note": noted,
            "has_source_expression": has_src,
            "mutants_applied": len(mutants),
            "mutants_caught": len(mutants) - len(survivors),
            "mutant_survivors": survivors,
            "dial_pointers": pointers,
            "dial_pointers_unresolved": unresolved,
        }
        print(
            f"  {design_id:6s} {base['ok'] and 'OK      ' or 'REJECTED'} "
            f"preset={str(spec.get('preset')):32s} leaves={len(leaves)} "
            f"noted={noted} src={int(has_src)} mutants={len(mutants) - len(survivors)}"
            f"/{len(mutants)} dials={len(pointers)} warn={len(base['warnings'])}"
        )

    covered = sorted(p for p in presets_claimed if p in REQUIRED_PRESETS)
    uncovered = sorted(p for p in REQUIRED_PRESETS if p not in presets_claimed)

    # Informational only, NOT gated: how the shared directory looks as a whole right now.
    sibling_ok = sibling_bad = 0
    for name in co_located:
        try:
            with open(os.path.join(HERE, name), "r", encoding="utf-8") as fh:
                if validate_spec(json.load(fh))["ok"]:
                    sibling_ok += 1
                else:
                    sibling_bad += 1
        except (OSError, json.JSONDecodeError):
            sibling_bad += 1

    report.update(
        {
            "slice": "council presets 33-48 (C-D33..C-D45, C-X46..C-X48) of the 72 designs in "
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
            "expected_count": len(EXPECTED_IDS),
            "measured_count": len(mine),
            "files_owned_by_this_unit": mine,
            "co_located_files_from_other_lanes": {
                "count": len(co_located),
                "validator_ok": sibling_ok,
                "validator_rejected": sibling_bad,
                "note": "This directory is shared with the other three preset lanes. These files are "
                "NOT gated by this probe - the counts are a courtesy signal for the "
                "orchestrator, measured with the same validator, and any rejection there "
                "belongs to the lane that authored it.",
            },
            "validator_command": "cd platform/lib && python -m councilspec "
            "../council/presets/<file>.councilspec.json",
            "validator_result": f"{sum(1 for v in per_file.values() if v['validator'] == 'OK')}"
            f"/{len(per_file)} OK",
            "mutation_battery": {
                "mutants_applied": mut_total,
                "mutants_caught": mut_caught,
                "survivors": sum(len(v["mutant_survivors"]) for v in per_file.values()),
                "benign_control_passed": f"{controls_passed[0]}/{len(per_file)}",
                "note": "both-states control: every applicable single-change mutant must flip the "
                "file from OK to REJECTED (the REJECT branch), and a benign edit to the same "
                "file must still validate (the OK branch). Without the benign control, a "
                "0-survivor result would be silent in both states - it could equally mean "
                "the harness corrupts every mutant.",
            },
            "dial_pointers_checked": pointer_total,
            "required_preset_coverage": {
                "claimed_by_this_slice": covered,
                "not_claimed_by_this_slice": uncovered,
                "note": "This is 16 of 64 presets; the remaining names are other lanes' to cover. "
                "`custom` entries are deliberate: see each file's PRESET-NAME note.",
            },
            "preset_name_usage": {
                k: sorted(v) for k, v in sorted(presets_claimed.items())
            },
            "extends_preset_lineage_only": {
                k: sorted(v) for k, v in sorted(lineage_refs.items())
            },
            "per_file": per_file,
            "problems": problems,
            "status": "PASS" if not problems else "FAIL",
        }
    )

    with open(
        os.path.join(HERE, "LANE-3-PRESET-VALIDATION.json"), "w", encoding="utf-8"
    ) as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")

    print(
        f"\nmutation battery : {mut_caught}/{mut_total} mutants caught, "
        f"{mut_total - mut_caught} survived; benign control passed "
        f"{controls_passed[0]}/{len(per_file)} (proves the OK branch is reachable)"
    )
    print(
        f"dial pointers    : {pointer_total} checked, all resolve"
        if not any(v["dial_pointers_unresolved"] for v in per_file.values())
        else f"dial pointers    : {pointer_total} checked, SOME UNRESOLVED"
    )
    print(f"required presets : {len(covered)} of 24 claimed by this slice -> {covered}")

    if problems:
        print()
        for p in problems:
            print(f"  - {p}")
        print(f"FAILED:preset-validation {len(problems)} problem(s)")
        return 1
    print(
        f"SUCCESS:preset-validation {len(mine)}/{len(EXPECTED_IDS)} presets validate; "
        f"{mut_caught}/{mut_total} mutants caught; {pointer_total} dial pointers resolve"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
