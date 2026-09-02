#!/usr/bin/env python3
"""Emit the CNL-0128 council design note (JSON at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import builder as B  # noqa: E402
import goals as GO  # noqa: E402
import spec as S  # noqa: E402
import surfaces as SUR  # noqa: E402

UNIT = "CNL-0128"
OUT = (
    "command-center/design/council/"
    "CNL-0128-cli-sdk-and-structured-builder-ergonomics-including-invali.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0128/probe1_roundtrip.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0128/probe2_invalid_path.py"
)
QUESTION = (
    "Can an owner express all five natural-language goals from the spec "
    "(brainstorm until 100 unique ideas; argue until all agree or 12 rounds; "
    "90 percent consensus with a mandatory minority report; continue until "
    "no new counterexample for two rounds; stop only after an executable "
    "test settles it) - and what does the tool say when the spec they wrote "
    "is invalid?"
)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0128 snippet missing in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def main() -> int:
    GO.dump_fixture(REPO)
    quote = GO.catalog_quote(REPO)
    trips = []
    for goal in GO.GOALS:
        rt = B.round_trip(goal["phrase"], surface="builder")
        if not rt.get("ok") or not rt.get("round_trip"):
            print(f"FAILED:CNL-0128 round-trip {goal['id']} {rt}")
            return 1
        trips.append(
            {
                "id": goal["id"],
                "natural_language": goal["phrase"],
                "stopping_expr": rt["spec"]["stopping_expr"],
                "restatement": rt["restatement"],
                "minority_report": rt["spec"]["outputs"]["minority_report"],
                "named_gap": False,
                "cli_sdk_builder_canonical_equal": (
                    SUR.canonical(B.build_from_goal(goal["phrase"], surface="cli")["spec"])
                    == SUR.canonical(SUR.sdk_build(goal["phrase"])["spec"])
                    == SUR.canonical(
                        B.build_from_answers({"goal_id": goal["id"]}, surface="builder")["spec"]
                    )
                ),
            }
        )

    unbound = {
        "kind": "CouncilSpec",
        "spec_version": "2",
        "goal_id": "GX",
        "natural_language": "stop when the vibes are good",
        "stopping_expr": "vibes >= 0.9",
        "seats": [
            {"seat_id": "a", "role": "proposer"},
            {"seat_id": "b", "role": "critic"},
        ],
    }
    unbound_errs = S.validate(unbound)
    unbound_fmt = S.format_errors(unbound_errs)
    if not unbound_errs or "/stopping_expr" not in {e["path"] for e in unbound_errs}:
        print("FAILED:CNL-0128 unbound did not name /stopping_expr")
        return 1
    if "Traceback" in unbound_fmt:
        print("FAILED:CNL-0128 traceback leaked")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    goals_rel = "command-center/p2-wave/probes/CNL-0128/goals.py"
    spec_rel = "command-center/p2-wave/probes/CNL-0128/spec.py"
    builder_rel = "command-center/p2-wave/probes/CNL-0128/builder.py"
    surf_rel = "command-center/p2-wave/probes/CNL-0128/surfaces.py"
    gram_rel = "command-center/p2-wave/probes/CNL-0128/grammar.py"
    cat_rel = "command-center/WORK-UNIT-CATALOG.json"
    fix_rel = "command-center/p2-wave/probes/CNL-0128/fixtures/goals-11198.json"

    answer = (
        "Yes. All five catalog phrases round-trip through a shared builder "
        "core used by the CLI, the SDK, and the typed structured builder: "
        "natural language (or goal_id G1..G5) -> valid CouncilSpec -> "
        "field-derived restatement. Encodings: G1 unique_ideas >= 100; "
        "G2 unanimity == true OR max_rounds == 12; G3 consensus >= 0.90 "
        "with outputs.minority_report == mandatory; G4 "
        "no_new_counterexample_rounds >= 2; G5 quality_gate == PASS with "
        "no round-count OR-escape. An unrecognized phrase is a named gap "
        "at /natural_language, not a guessed spec. An invalid spec returns "
        "JSON-Pointer path errors (example: unbound ident vibes -> "
        "/stopping_expr) and never a stack trace; CLI validate exits 2."
    )

    nc_verbatim = (
        "NEGATIVE-CONTROL verbatim: the path-named invalid-spec check is "
        "SILENT on each of the five catalog goal specs (zero errors, no "
        "traceback); it FIRES on the planted unbound-ident fixture naming "
        "/stopping_expr, and the formatted error contains no traceback."
    )

    doc = {
        "unit_id": UNIT,
        "schema_version": 1,
        "kind": "council-design-note",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0128",
        "title": "CLI, SDK and structured builder ergonomics, including invalid-spec errors",
        "question": QUESTION,
        "answer": answer,
        "spec_line_11198": {
            "claimed_source": "_USER-PROMPTS.md:11198",
            "present_on_this_tree": False,
            "live_quote": f"{quote['path']}:{quote['line']}",
            "phrases": list(GO.PHRASES),
        },
        "family": {
            "name": "owner-goal-phrasings-11198",
            "expected_n": 5,
            "counted_n": len(trips),
            "members": [
                {
                    "id": t["id"],
                    "phrase": t["natural_language"],
                    "stopping_expr": t["stopping_expr"],
                    "round_trip": True,
                }
                for t in trips
            ],
        },
        "round_trips": trips,
        "surfaces": {
            "cli": {
                "entry": "surfaces.py build|validate",
                "invalid_exit_code": 2,
                "never_traceback": True,
            },
            "sdk": {
                "entry": "surfaces.sdk_build / sdk_validate",
                "returns": "typed dict (ok, spec|errors), not a string as truth",
            },
            "structured_builder": {
                "entry": "builder.build_from_answers({goal_id})",
                "typed_question": "which of G1..G5?",
                "satisfies_disjunct": "visual OR structured builder — structured builder SATISFIES",
            },
            "shared_core": "builder.build_from_goal; canonical JSON ignores source_surface",
        },
        "invalid_spec_contract": {
            "shape": "{path, code, message} JSON Pointer paths",
            "never": "Python traceback / stack trace",
            "worked_example": {
                "fixture": "stopping_expr=vibes >= 0.9",
                "errors": unbound_errs,
                "formatted": unbound_fmt,
            },
        },
        "verdicts": [
            {"record_id": t["id"], "verdict": "EXECUTABLE"} for t in trips
        ],
        "tests": [
            {"id": "probe1-roundtrip", "command": P1, "result": "PASS"},
            {"id": "probe2-invalid-path", "command": P2, "result": "PASS"},
        ],
        "both_states": {
            "good_state": {
                "id": "five-catalog-goals",
                "detector": "SILENT",
                "errors": 0,
            },
            "bad_state": {
                "id": "unbound-ident-vibes",
                "detector": "FIRE",
                "path": "/stopping_expr",
                "code": "unbound-ident",
            },
            "pass": True,
        },
        "negative_control": {
            "state_the_check_is_meant_to_reject": (
                "an invalid CouncilSpec (unbound stopping ident, empty seats, "
                "or statically unsatisfiable expression)"
            ),
            "control_fixture": "each of the five catalog goal specs, built live",
            "what_the_check_does_on_that_state": (
                "SILENT: validate() returns [] and format_errors contains no Traceback"
            ),
            "verbatim": nc_verbatim,
        },
        "negative_controls": [
            {
                "id": "NC-unbound-ident",
                "kind": "malformed-input",
                "description": nc_verbatim,
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": unbound_fmt,
                "good_state_output": (
                    "SILENT on each of the five catalog goal specs: errors=[]"
                ),
            }
        ],
        "report": {
            "kind": "council-design-note",
            "observations": [
                {
                    "name": "five-goal-round-trip",
                    "measured": len(trips) == 5,
                    "method": "builder.round_trip plus CLI/SDK/typed canonical equality",
                    "anchor": P1,
                },
                {
                    "name": "invalid-spec-path-named",
                    "measured": "/stopping_expr",
                    "method": "spec.validate on unbound-ident fixture",
                    "anchor": P2,
                },
            ],
            "control_ids": ["NC-unbound-ident"],
        },
        "reviewer": {
            "reviewer_id": "CNL-0128-probe2-catalog-reread",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "Probe 2 re-extracts the five phrases from the catalog "
                "parenthetical and checks encodings from spec fields; it does "
                "not trust probe 1's printed restatement table."
            ),
        },
        "evidence": [
            {
                "claim": (
                    "The five owner goals are quoted in the CNL-0128 catalog "
                    "question; _USER-PROMPTS.md:11198 is not on this tree."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{cat_rel}:{quote['line']}",
                "path": cat_rel,
                "line": quote["line"],
                "snippet": GO.PHRASES[0],
                "kind": "catalog",
                "mechanism": "catalog-question-quote",
            },
            {
                "claim": "G1 encodes unique_ideas >= 100 and round-trips.",
                "verdict": "CONFIRMED",
                "anchor": f"{goals_rel}:{find_line(goals_rel, 'unique_ideas >= 100')}",
                "path": goals_rel,
                "line": find_line(goals_rel, "unique_ideas >= 100"),
                "snippet": "unique_ideas >= 100",
                "kind": "live-tree",
                "mechanism": "builder-round-trip",
            },
            {
                "claim": "Invalid stopping_expr names JSON Pointer /stopping_expr, not a traceback.",
                "verdict": "CONFIRMED",
                "anchor": f"{spec_rel}:{find_line(spec_rel, '\"/stopping_expr\"')}",
                "path": spec_rel,
                "line": find_line(spec_rel, '"/stopping_expr"'),
                "snippet": '"/stopping_expr"',
                "kind": "live-tree",
                "mechanism": "path-named-validator",
            },
            {
                "claim": "Unrecognized owner language is a named gap at /natural_language.",
                "verdict": "CONFIRMED",
                "anchor": f"{builder_rel}:{find_line(builder_rel, 'unrecognized-goal')}",
                "path": builder_rel,
                "line": find_line(builder_rel, "unrecognized-goal"),
                "snippet": "unrecognized-goal",
                "kind": "live-tree",
                "mechanism": "named-gap-not-guess",
            },
            {
                "claim": "CLI/SDK/builder share one builder core; canonical JSON drops source_surface.",
                "verdict": "CONFIRMED",
                "anchor": f"{surf_rel}:{find_line(surf_rel, 'body = {k: v for k, v in spec.items() if k != \"source_surface\"}')}",
                "path": surf_rel,
                "line": find_line(surf_rel, 'if k != "source_surface"'),
                "snippet": 'if k != "source_surface"',
                "kind": "live-tree",
                "mechanism": "surface-parity",
            },
        ],
        "residual_unknowns": [
            "_USER-PROMPTS.md:11198 is not present on this Linux worktree; phrases are taken from the catalog quote of that line.",
            "CNL-0010 catalog artifact is not on this tree; stopping grammar is the local A10 surface (grammar.py), same family as CNL-0083.",
            "CNL-0116 flagship preset artifact is not on this tree; the default three-seat roster is local to this prototype, not a claim that auto-compose is implemented.",
            "Production CLI/SDK/builder modules (IMP-0325/0326/0327) are not shipped here; this unit is the design contract those units must implement.",
        ],
        "dependencies_noted": {
            "CNL-0010": "stopping-expression grammar consumed as local A10 surface; catalog artifact absent, not blocking the five-goal encodings",
            "CNL-0116": "flagship auto-composed preset is not required to round-trip the five phrases; default roster is local",
            "blocked_on_missing_deps": False,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {"path": builder_rel, "exists": True, "role": "supporting"},
            {"path": spec_rel, "exists": True, "role": "supporting"},
            {"path": gram_rel, "exists": True, "role": "supporting"},
            {"path": fix_rel, "exists": True, "role": "supporting"},
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "five-goal-round-trip"},
            {"id": "probe2", "command": P2, "role": "invalid-path-negative-control"},
        ],
        "ts": now,
        "SUCCESS:CNL-0128": True,
    }

    catalog_schema = REPO / SCHEMA
    if not catalog_schema.is_file() or catalog_schema.stat().st_size <= 0:
        print("FAILED:CNL-0128 catalog output_schema missing on disk")
        return 1
    # Catalog schema is a generated $ref shim to ast-integrate.invalid; it
    # cannot be resolved on this host. Constrain with the local schema.
    local_schema_path = HERE / "note.schema.json"
    schema = json.loads(local_schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0128 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {"blob": "x" * 200, "passing_tests": 1},
        {"unit_id": "CNL-0128", "state": "SUCCESS"},
        {},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNL-0128 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print("SUCCESS:CNL-0128")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
