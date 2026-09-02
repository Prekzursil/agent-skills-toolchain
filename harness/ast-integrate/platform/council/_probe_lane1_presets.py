"""Lane-1 preset gate: validate, prove executable, and prove the detector fires.

Six checks, all mechanical. Anything a loop can settle is settled by the loop.

1. INVENTORY   - the 17 lane-1 files exist (explicit list; a missing file FAILS
                 CLOSED, an empty directory can never read as a pass).
2. VALIDATE    - each file passes councilspec schema + semantic validation with
                 zero ERRORs and zero WARNings.
3. IDENTITY    - council_id equals the filename stem, and every id is unique.
4. HUMAN-FORM  - every preset carries a `HUMAN-STOP:` line and an
                 `EDITABLE-DIALS:` line in metadata.notes, and the HUMAN-STOP
                 string PARSES TO THE SAME TREE as stopping.expression once the
                 documentation-only `note`/`producer` keys are stripped. This is
                 the equivalence proof for the 12 presets that cannot use
                 `stopping.source_expression` (SEM-001 compares by exact dict
                 equality, so a leaf carrying `note` or `producer` can never
                 equal the parsed string - a measured, documented constraint).
5. BOTH-STATES - each stopping rule is EXECUTED against a satisfying snapshot
                 (must return True) and a falsifying one (must return False). A
                 rule that cannot be made false measures nothing.
6. DETECTOR    - six mutations of real presets must be REJECTED (or, for the
                 advisory rule, must raise a warning). A validator never shown
                 to fire on a known-broken input is not evidence.

Run:  python platform/council/_probe_lane1_presets.py
"""

from __future__ import annotations

import copy
import json
import os
import sys
from typing import Any, Dict, List, Mapping, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
PRESETS = os.path.join(HERE, "presets")
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))

from councilspec.expression import evaluate, iter_leaves, parse  # noqa: E402
from councilspec.registry import SCHEMA_PATH, load_schema  # noqa: E402
from councilspec.validate import validate_spec  # noqa: E402

# Lane 1 = the first 16 rows of the doc-12 "Preset index" table, plus one
# spec-required preset that has no design row anywhere in the 72 (see the file's
# own metadata.notes for why it is numbered 73 and why it is not a renumbering).
LANE1_SLICE = [
    "c-m01-micro-triage-2seat",
    "c-m02-micro-go-nogo-3voice",
    "c-m03-micro-single-claim-adjudication",
    "c-m04-micro-second-opinion-crossvendor",
    "c-m05-micro-premortem-solo-plus-critic",
    "c-m06-micro-assumption-check",
    "c-m07-micro-scope-guard",
    "c-m08-micro-cost-sanity",
    "c-m09-micro-security-smell",
    "c-m10-micro-should-we-stop",
    "c-s11-design-gate-5",
    "c-s12-plan-gate-3-adversarial",
    "c-s13-council-4voice-classic",
    "c-s14-critique-panel-rubric",
    "c-s15-arch-review-board-5",
    "c-s16-peer-review-3-blind",
]
LANE1_ADDITIONS = ["c-g73-general-purpose-auto-composed"]
EXPECTED = LANE1_SLICE + LANE1_ADDITIONS

ANNOTATION_KEYS = ("note", "producer")


def path_for(stem: str) -> str:
    return os.path.join(PRESETS, f"{stem}.councilspec.json")


def strip_annotations(node: Any) -> Any:
    """Drop documentation-only keys so a tree can be compared to a parsed one."""
    if isinstance(node, Mapping):
        return {
            k: strip_annotations(v) for k, v in node.items() if k not in ANNOTATION_KEYS
        }
    if isinstance(node, list):
        return [strip_annotations(v) for v in node]
    return node


def notes_field(spec: Mapping[str, Any], label: str) -> str | None:
    notes = (spec.get("metadata") or {}).get("notes") or ""
    if label not in notes:
        return None
    tail = notes.split(label, 1)[1]
    return tail.split(" | ")[0].strip()


def _enum_alternatives() -> List[str]:
    schema = load_schema(SCHEMA_PATH)
    return list(schema["$defs"]["stop_leaf_enum"]["properties"]["value"]["enum"])


ENUM_TOKENS = _enum_alternatives()


def _leaf_value(leaf: Mapping[str, Any], want: bool) -> Any:
    """A snapshot value making this leaf True (want) or False (not want)."""
    op, val = leaf["op"], leaf["value"]
    if isinstance(val, bool):
        truth = val if op == "==" else not val
        return truth if want else not truth
    if isinstance(val, str):
        other = next(t for t in ENUM_TOKENS if t != val)
        truth = val if op == "==" else other
        return truth if want else (other if op == "==" else val)
    table_true = {
        ">=": val,
        ">": val + 1,
        "<=": val,
        "<": val - 1,
        "==": val,
        "!=": val + 1,
    }
    table_false = {
        ">=": val - 1,
        ">": val,
        "<=": val + 1,
        "<": val,
        "==": val + 1,
        "!=": val,
    }
    return (table_true if want else table_false)[op]


def snapshot(tree: Mapping[str, Any], want: bool) -> Tuple[Dict[str, Any], List[str]]:
    """Build a metric snapshot; report metrics constrained more than once."""
    out: Dict[str, Any] = {}
    conflicts: List[str] = []
    for leaf in iter_leaves(tree):
        metric, value = leaf["metric"], _leaf_value(leaf, want)
        if metric in out and out[metric] != value:
            conflicts.append(metric)
        out[metric] = value
    return out, conflicts


def has_not_node(node: Mapping[str, Any]) -> bool:
    if "not" in node:
        return True
    for key in ("all_of", "any_of"):
        if key in node:
            return any(has_not_node(child) for child in node[key])
    if "weighted" in node:
        return any(has_not_node(c["when"]) for c in node["weighted"]["clauses"])
    return False


# ----------------------------------------------------------------- mutations


def _mut_unknown_key(spec):
    spec["_comment"] = "JSON has no comments; can an extra key carry one?"
    return spec


def _mut_count_incoherent(spec):
    spec["participants"]["count"]["min"] = 99
    return spec


def _mut_note_on_source_expression_leaf(spec):
    tree = spec["stopping"]["expression"]
    target = tree["any_of"][0] if "any_of" in tree else tree["all_of"][0]
    target["note"] = "documentation on a leaf of a source_expression preset"
    return spec


def _mut_drop_impossibility_outcome(spec):
    spec["outcomes"]["allowed"] = [
        o for o in spec["outcomes"]["allowed"] if o != "proof_of_impossibility"
    ]
    return spec


def _mut_dangling_chair(spec):
    spec["topology"]["chair"] = "no-such-seat"
    return spec


def _mut_drop_producer(spec):
    for leaf in iter_leaves(spec["stopping"]["expression"]):
        if leaf["metric"].startswith("custom:"):
            leaf.pop("producer", None)
    return spec


# (stem, label, mutator, expectation) - expectation is "reject" or "warn"
MUTATIONS = [
    (
        "c-m01-micro-triage-2seat",
        "unknown top-level key (no JSON comments)",
        _mut_unknown_key,
        "reject",
    ),
    (
        "c-m01-micro-triage-2seat",
        "count.min > count.max (SEM-002)",
        _mut_count_incoherent,
        "reject",
    ),
    (
        "c-m01-micro-triage-2seat",
        "leaf note beside source_expression (SEM-001)",
        _mut_note_on_source_expression_leaf,
        "reject",
    ),
    (
        "c-s15-arch-review-board-5",
        "impossibility outcome removed (SEM-009)",
        _mut_drop_impossibility_outcome,
        "reject",
    ),
    (
        "c-s15-arch-review-board-5",
        "topology.chair dangling id (SEM-006)",
        _mut_dangling_chair,
        "reject",
    ),
    (
        "c-m03-micro-single-claim-adjudication",
        "custom leaf loses producer (SEM-012)",
        _mut_drop_producer,
        "warn",
    ),
]

REQUIRED_PRESET_NAMES = [
    n for n in load_schema(SCHEMA_PATH)["$defs"]["preset_name"]["enum"] if n != "custom"
]


def main() -> int:
    failures: List[str] = []
    per_file: Dict[str, Any] = {}
    specs: Dict[str, Any] = {}

    # 1. INVENTORY - fail closed on a missing file or an empty directory.
    missing = [s for s in EXPECTED if not os.path.isfile(path_for(s))]
    if missing:
        failures.append(f"missing preset files: {missing}")
    print(f"[1] inventory   expected={len(EXPECTED)} missing={len(missing)}")

    for stem in EXPECTED:
        p = path_for(stem)
        if not os.path.isfile(p):
            continue
        with open(p, "r", encoding="utf-8") as fh:
            specs[stem] = json.load(fh)

    # 2. VALIDATE
    clean = 0
    for stem, spec in specs.items():
        res = validate_spec(spec)
        entry = {
            "schema_ok": res["schema_ok"],
            "schema_errors": res["schema_errors"],
            "semantic_errors": res["semantic_errors"],
            "warnings": res["warnings"],
            "verdict": "OK" if res["ok"] and not res["warnings"] else "REVIEW",
        }
        per_file[stem] = entry
        if res["ok"] and not res["warnings"]:
            clean += 1
        else:
            failures.append(
                f"{stem}: {res['schema_errors'] + res['semantic_errors'] + res['warnings']}"
            )
    print(f"[2] validate    clean={clean}/{len(specs)} (zero errors AND zero warnings)")

    # 3. IDENTITY
    ids = {}
    for stem, spec in specs.items():
        cid = spec.get("council_id")
        if cid != stem:
            failures.append(f"{stem}: council_id {cid!r} != filename stem")
        ids.setdefault(cid, []).append(stem)
    dupes = {k: v for k, v in ids.items() if len(v) > 1}
    if dupes:
        failures.append(f"duplicate council_id: {dupes}")
    print(f"[3] identity    unique_ids={len(ids)} dupes={len(dupes)}")

    # 4. HUMAN-FORM equivalence + documented dials
    equiv = 0
    for stem, spec in specs.items():
        human = notes_field(spec, "HUMAN-STOP:")
        dials = notes_field(spec, "EDITABLE-DIALS:")
        if not human:
            failures.append(f"{stem}: no HUMAN-STOP line in metadata.notes")
            continue
        if not dials:
            failures.append(f"{stem}: no EDITABLE-DIALS line in metadata.notes")
        bare = strip_annotations(spec["stopping"]["expression"])
        try:
            parsed = parse(human)
        except Exception as exc:  # noqa: BLE001 - report, never crash the gate
            failures.append(f"{stem}: HUMAN-STOP does not parse: {exc}")
            continue
        if parsed != bare:
            failures.append(f"{stem}: HUMAN-STOP parses to a different tree")
            continue
        per_file[stem]["human_stop"] = human
        per_file[stem]["human_stop_equivalent"] = True
        equiv += 1
    print(f"[4] human-form  equivalent={equiv}/{len(specs)}")

    # 5. BOTH-STATES execution
    executed = 0
    for stem, spec in specs.items():
        tree = strip_annotations(spec["stopping"]["expression"])
        yes, c1 = snapshot(tree, True)
        no, c2 = snapshot(tree, False)
        if c1 or c2:
            failures.append(
                f"{stem}: metric constrained twice, snapshot ambiguous: {c1 + c2}"
            )
            continue
        if has_not_node(tree):
            failures.append(
                f"{stem}: NOT node present; the all-false snapshot is not a proof"
            )
            continue
        got_yes, got_no = evaluate(tree, yes), evaluate(tree, no)
        if got_yes is not True or got_no is not False:
            failures.append(
                f"{stem}: both-states failed (satisfy={got_yes}, falsify={got_no})"
            )
            continue
        per_file[stem]["both_states"] = "satisfy=True falsify=False"
        executed += 1
    print(f"[5] both-states executed={executed}/{len(specs)}")

    # 6. DETECTOR control - the validator must fire on known-broken input
    fired = 0
    control_rows = []
    for stem, label, mutate, expect in MUTATIONS:
        base = specs.get(stem)
        if base is None:
            failures.append(f"mutation base missing: {stem}")
            continue
        res = validate_spec(mutate(copy.deepcopy(base)))
        if expect == "reject":
            ok = not res["ok"]
            detail = (res["schema_errors"] + res["semantic_errors"] or ["<silent>"])[0]
        else:
            ok = res["ok"] and bool(res["warnings"])
            detail = (res["warnings"] or ["<silent>"])[0]
        control_rows.append(
            {
                "base": stem,
                "mutation": label,
                "expect": expect,
                "fired": ok,
                "detail": detail[:160],
            }
        )
        if ok:
            fired += 1
            print(f"    [{expect.upper():6}] {label} -> {detail[:110]}")
        else:
            failures.append(f"DETECTOR SILENT on {label} ({stem})")
            print(f"    [SILENT] {label}  <- the gate did not fire")
    print(f"[6] detector    fired={fired}/{len(MUTATIONS)}")

    # Coverage of the schema's required preset-name vocabulary.
    used = sorted({s.get("preset") for s in specs.values()} - {None, "custom"})
    not_in_slice = [n for n in REQUIRED_PRESET_NAMES if n not in used]
    on_disk = sorted(
        f[: -len(".councilspec.json")]
        for f in os.listdir(PRESETS)
        if f.endswith(".councilspec.json")
    )
    foreign = [f for f in on_disk if f not in EXPECTED]

    status = {
        "unit": "build/preset-1",
        "phase": "2C",
        "slice": "council presets 1-16 of 64",
        "state": "MEASURED" if not failures else "MEASURED - WITH FAILURES",
        "design_source": (
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.md"
        ),
        "validated_against": (
            "C:/Users/Prekzursil/source/ast-integrate/platform/schema/"
            "councilspec.schema.json"
        ),
        "slice_mapping": {
            "basis": (
                "doc-12 'Preset index' table order (C-M01..C-M10, C-S11..C-S30, "
                "C-D31..C-D45, C-X46..C-X51, C-H52..C-H72 = 72 rows); the four "
                "build lanes take the first 64, 16 each"
            ),
            "index_1": "C-M01 micro-triage-2seat",
            "index_16": "C-S16 peer-review-3-blind",
            "sibling_corroboration": (
                "LANE-2-STATUS.json declares 17-32, PRESET-VALIDATION.json 33-48, "
                "PRESETS-MANIFEST.json 49-64"
            ),
        },
        "files": [f"{s}.councilspec.json" for s in EXPECTED],
        "counts": {
            "slice_files": len(LANE1_SLICE),
            "addition_files": len(LANE1_ADDITIONS),
            "files_written": len(specs),
            "files_clean_zero_errors_zero_warnings": clean,
            "human_stop_equivalent": equiv,
            "both_states_executed": executed,
            "mutations_caught": fired,
            "mutations_total": len(MUTATIONS),
            "other_lane_files_in_this_directory": len(foreign),
        },
        "required_preset_coverage": {
            "vocabulary_source": "councilspec.schema.json $defs.preset_name.enum minus 'custom'",
            "covered_by_this_lane": used,
            "not_in_this_slice": not_in_slice,
        },
        "validator_output_per_file": per_file,
        "both_states_control": control_rows,
        "foreign_files_seen": foreign,
        "failures": failures,
    }
    with open(
        os.path.join(PRESETS, "LANE-1-STATUS.json"), "w", encoding="utf-8", newline="\n"
    ) as fh:
        json.dump(status, fh, indent=2, ensure_ascii=True)
        fh.write("\n")

    print(f"    preset-name coverage: {used}")
    print(f"    not in this slice   : {not_in_slice}")
    print(f"    foreign files in dir: {len(foreign)}")
    if failures:
        for f in failures:
            print(f"FAIL {f}")
        print(f"FAILED:lane1-presets {len(failures)} failure(s)")
        return 1
    print(
        f"SUCCESS:lane1-presets {len(specs)} presets "
        f"({len(LANE1_SLICE)} slice + {len(LANE1_ADDITIONS)} addition) "
        f"clean={clean} equiv={equiv} both_states={executed} "
        f"mutations_caught={fired}/{len(MUTATIONS)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
