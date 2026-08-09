"""Gate for the editable CouncilSpec preset library, lane build/preset-4.

Scope note (measured, not assumed): platform/council/presets/ is SHARED - three sibling
preset lanes write into it concurrently, using two different filename conventions
(`c-m01-...` and `C-D33-...`). This gate therefore polices ONLY the doc ids this lane owns
(global ordinals 49-64 plus one spec-required gap-closer) and never reports a sibling's file
as unlisted. A gate that failed on a sibling's in-flight write would be a broken detector.

Every preset this lane owns must clear FIVE independent checks, not one:

1. JSON Schema (Draft 2020-12) against platform/schema/councilspec.schema.json.
2. The semantic rules in councilspec.semantics (SEM-001..SEM-012), zero ERRORs.
3. `parse(stopping.source_expression) == stopping.expression` - the readable form and the
   executed tree are the same tree, so the documentation cannot lie. SEM-001 also checks
   this; asserting it here means the gate still fails if SEM-001 is ever weakened.
4. `parse(unparse(expression)) == expression` - tree-level round-trip idempotence.
5. A BOTH-STATES control on the stopping rule: True on the manifest's `metrics_satisfying`
   snapshot and False on `metrics_not_satisfying`. A rule true in both states measures
   nothing, so a preset without both probes is a FAILURE, not a skip.

Plus bookkeeping that fails closed: a missing owned doc id, an owned file absent from the
manifest, a manifest entry with no file, an empty walk, or a warning set that differs from
the declared one.

Run:
    python platform/council/validate_presets.py
    python platform/council/validate_presets.py --json platform/council/LANE-4-PRESET-VALIDATION.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "lib"))
if LIB not in sys.path:
    sys.path.insert(0, LIB)

from councilspec.expression import evaluate, parse, unparse  # noqa: E402
from councilspec.registry import load_schema  # noqa: E402
from councilspec.validate import validate_file  # noqa: E402

PRESETS_DIR = os.path.join(HERE, "presets")
MANIFEST = os.path.join(PRESETS_DIR, "LANE-4-MANIFEST.json")

# Global ordinals 49-64 of the 72 designs in 12-COUNCIL-PROTOCOLS-AND-PRESETS.md, whose ids
# are a single global sequence (C-M01=1 ... C-H72=72), plus three GAP-* closers for REQUIRED
# preset names that a measured cross-lane scan found covered by zero files:
#   GAP-AUTO    general_purpose_auto_composed - absent from all 72 designs
#   GAP-WATCH   standing_watch_council        - absent from all 72 designs
#   GAP-ROADMAP roadmap_prioritization        - design C-H65 exists but ordinals 65-72 are
#                                               outside the 64-preset budget, so no lane owns it
# A missing required name is a spec failure; a duplicate is a cosmetic dedupe. See
# _probe_union_preset_coverage.py for the measurement that motivated all three.
OWNED_DOC_IDS: List[str] = [
    "C-X49",
    "C-X50",
    "C-X51",
    "C-H52",
    "C-H53",
    "C-H54",
    "C-H55",
    "C-H56",
    "C-H57",
    "C-H58",
    "C-H59",
    "C-H60",
    "C-H61",
    "C-H62",
    "C-H63",
    "C-H64",
    "GAP-ROADMAP",
    "GAP-WATCH",
    "GAP-AUTO",
]


def required_preset_names() -> List[str]:
    """The presets the spawn brief names as REQUIRED == the schema's preset_name enum minus
    the `custom` escape hatch. Read out of the schema so the two cannot drift."""
    schema = load_schema()
    return [n for n in schema["$defs"]["preset_name"]["enum"] if n != "custom"]


def _warn_ids(result: Dict[str, Any]) -> List[str]:
    return sorted({w.split()[1] for w in result["warnings"]})


def _doc_id_of(filename: str) -> str:
    """Leading doc-id token of an owned filename, e.g. C-X49-mega-... -> C-X49."""
    parts = filename.split("-")
    return "-".join(parts[:2]).upper() if len(parts) >= 2 else filename.upper()


def check_one(entry: Dict[str, Any]) -> Dict[str, Any]:
    rel = entry["file"]
    path = os.path.join(PRESETS_DIR, rel)
    out: Dict[str, Any] = {
        "file": rel,
        "doc_id": entry.get("doc_id"),
        "ordinal": entry.get("ordinal"),
        "problems": [],
    }
    if not os.path.isfile(path):
        out["problems"].append("MISSING on disk")
        return out

    res = validate_file(path)
    out["schema_errors"] = res["schema_errors"]
    out["semantic_errors"] = res["semantic_errors"]
    out["warnings"] = _warn_ids(res)
    if not res["ok"]:
        out["problems"].append(
            "rejected: " + " | ".join(res["schema_errors"] + res["semantic_errors"])
        )
        return out

    expected_warn = sorted(entry.get("expected_warnings", []))
    if out["warnings"] != expected_warn:
        out["problems"].append(
            f"warnings {out['warnings']} != declared {expected_warn}"
        )

    with open(path, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    out["preset"] = spec.get("preset")
    out["council_id"] = spec.get("council_id")
    tree = spec["stopping"]["expression"]
    src = spec["stopping"].get("source_expression")

    if not src:
        out["problems"].append(
            "no source_expression: the readable form is unverifiable"
        )
    else:
        out["source_expression"] = src
        if parse(src) != tree:
            out["problems"].append(
                "source_expression does not parse to stopping.expression"
            )
        if entry.get("source_expression") not in (None, src):
            out["problems"].append("manifest source_expression differs from the file")
    if parse(unparse(tree)) != tree:
        out["problems"].append("unparse/parse is not tree-idempotent")
    out["canonical_expression"] = unparse(tree)

    if spec.get("preset") != entry.get("preset"):
        out["problems"].append(
            f"file preset {spec.get('preset')!r} != manifest preset {entry.get('preset')!r}"
        )

    sat, unsat = entry.get("metrics_satisfying"), entry.get("metrics_not_satisfying")
    if sat is None or unsat is None:
        out["problems"].append(
            "both-states control absent; a stopping rule proven in one state measures nothing"
        )
    else:
        try:
            got_true = evaluate(tree, sat)
            got_false = evaluate(tree, unsat)
        except Exception as exc:  # a probe that cannot run is a failure, not a skip
            out["problems"].append(f"evaluation raised {exc!r}")
        else:
            out["eval"] = {"satisfying": got_true, "not_satisfying": got_false}
            if got_true is not True:
                out["problems"].append("metrics_satisfying did not stop the council")
            if got_false is not False:
                out["problems"].append(
                    "metrics_not_satisfying stopped the council anyway"
                )

    # Editability: a preset must be documented, not an opaque blob.
    notes = (spec.get("metadata") or {}).get("notes") or ""
    if len(notes) < 400:
        out["problems"].append(
            f"metadata.notes is {len(notes)} chars; a preset must document its dials, its "
            "vocabulary mapping and its custom metrics"
        )
    for token in ("EDITABLE DIALS", "SOURCE DESIGN"):
        if token not in notes:
            out["problems"].append(f"metadata.notes lacks a {token} section")
    if not (spec.get("objective") or {}).get("charter"):
        out["problems"].append(
            "objective.charter absent; the council has no written mandate"
        )
    if not (spec.get("metadata") or {}).get("spec_citations"):
        out["problems"].append(
            "metadata.spec_citations absent; the design lineage is unciteable"
        )
    out["notes_chars"] = len(notes)
    return out


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="validate_presets")
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args(argv)

    if not os.path.isfile(MANIFEST):
        print(f"FAILED:preset-gate manifest missing at {MANIFEST}")
        return 1
    with open(MANIFEST, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    cases = manifest.get("cases") or []
    if not cases:
        print(
            "FAILED:preset-gate manifest declares zero cases; an empty walk is a broken "
            "detector, not a pass"
        )
        return 1

    results = [check_one(entry) for entry in cases]

    listed = {os.path.normcase(c["file"]) for c in cases}
    owned_on_disk = {
        os.path.normcase(n)
        for n in os.listdir(PRESETS_DIR)
        if n.endswith(".councilspec.json") and _doc_id_of(n) in OWNED_DOC_IDS
    }
    unlisted = sorted(owned_on_disk - listed)
    phantom = sorted(listed - {os.path.normcase(n) for n in os.listdir(PRESETS_DIR)})
    declared_ids = [c.get("doc_id") for c in cases]
    missing_ids = [d for d in OWNED_DOC_IDS if d not in declared_ids]

    ok = (
        all(not r["problems"] for r in results)
        and not unlisted
        and not phantom
        and not missing_ids
    )

    width = max(len(r["file"]) for r in results)
    for r in results:
        status = "PASS " if not r["problems"] else "FAIL "
        extra = ""
        if not r["problems"]:
            ev = r.get("eval") or {}
            extra = (
                f"  preset={r.get('preset')}  eval=BOTH-STATES-OK"
                f"({ev.get('satisfying')}/{ev.get('not_satisfying')})"
                f"  warn={r.get('warnings')}  notes={r.get('notes_chars')}ch"
            )
        print(f"{status}{r['file']:<{width}}{extra}")
        for p in r["problems"]:
            print(f"      -> {p}")

    if unlisted:
        print(
            f"FAIL  owned preset files on disk but absent from the manifest: {unlisted}"
        )
    if phantom:
        print(f"FAIL  manifest entries with no file on disk: {phantom}")
    if missing_ids:
        print(f"FAIL  owned doc ids not yet authored: {missing_ids}")

    required = required_preset_names()
    covered = sorted(
        {
            r.get("preset")
            for r in results
            if r.get("preset") and r.get("preset") != "custom"
        }
    )
    missing = [n for n in required if n not in covered]
    sibling_files = sorted(
        n
        for n in os.listdir(PRESETS_DIR)
        if n.endswith(".councilspec.json") and _doc_id_of(n) not in OWNED_DOC_IDS
    )
    print()
    print(
        f"presets checked (this lane) : {len(results)} of {len(OWNED_DOC_IDS)} owned doc ids"
    )
    print(
        f"sibling files in shared dir : {len(sibling_files)} (not policed by this gate)"
    )
    print(f"required preset names        : {len(required)}")
    print(f"covered by THIS lane        : {len(covered)} -> {covered}")
    print(f"NOT covered here            : {len(missing)} -> {missing}")
    print(
        "  (one lane of four; the UNION across lanes is the orchestrator's gate, not this "
        "one - reported, never folded into a pass)"
    )

    summary = {
        "lane": manifest.get("lane"),
        "range": manifest.get("range"),
        "owned_doc_ids": OWNED_DOC_IDS,
        "presets_checked": len(results),
        "all_pass": ok,
        "unlisted_owned_files": unlisted,
        "phantom_entries": phantom,
        "owned_doc_ids_not_authored": missing_ids,
        "sibling_files_present": sibling_files,
        "required_preset_names": required,
        "covered_by_this_lane": covered,
        "not_covered_by_this_lane": missing,
        "results": results,
    }
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(summary, fh, indent=2)
            fh.write("\n")
        print(f"wrote {args.json_out}")

    print(
        "SUCCESS:preset-gate-lane-4"
        if ok
        else "FAILED:preset-gate-lane-4 at least one owned preset did not clear all checks"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
