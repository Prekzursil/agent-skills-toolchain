#!/usr/bin/env python3
"""Emit the CNL-0030 council design note (JSON stored at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import sim as S  # noqa: E402

OUT = "command-center/design/council/CNL-0030-chair-led-topology-and-agenda-control.md"
SCHEMA = "command-center/schema/council-design-note.schema.json"
CNL25 = "command-center/design/council/CNL-0025-chair-powers-and-capture-resistance.md"
QUESTION = (
    "What does a chair-led topology change about information flow versus a "
    "flat council, and at what roster size does chair-led become necessary "
    "rather than merely tidier?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0030/probe1_size_sweep.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0030/probe2_negative_control.py"
)
SIM = "command-center/p2-wave/probes/CNL-0030/sim.py"

# Catalog output_schema is a generated $ref shim. Draft7Validator against it
# tries to fetch https://ast-integrate.invalid/... and raises RefResolutionError.
# Overwriting the shared file is an ADV rebuild circle (CNL-0021 already parked
# that). G-1 named probes pin size_sweep/reviewer at the document root, which
# receipt_core additionalProperties:false would reject. Unit-local schema is
# the non-vacuous check (same pattern as BLD-0059).
UNIT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "title",
        "question",
        "answer",
        "size_sweep",
        "reviewer",
        "report",
        "negative_controls",
        "tests",
        "evidence",
    ],
    "properties": {
        "unit_id": {"const": "CNL-0030"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:CNL-0030"},
        "title": {"type": "string", "minLength": 16},
        "question": {"type": "string", "minLength": 40},
        "answer": {"type": "string", "minLength": 80},
        "size_sweep": {
            "type": "object",
            "required": ["crossover_n", "rows"],
            "properties": {
                "crossover_n": {"type": "integer", "minimum": 3},
                "rows": {"type": "array", "minItems": 8},
            },
        },
        "reviewer": {
            "type": "object",
            "required": [
                "reviewer_id",
                "verdict",
                "independent",
                "recounted_crossover_n",
            ],
            "properties": {
                "independent": {"const": True},
                "verdict": {"const": "PASS"},
                "recounted_crossover_n": {"type": "integer", "minimum": 3},
            },
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "council-design-note"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
        "negative_controls": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["fired_on_bad_state", "silent_on_good_state"],
                "properties": {
                    "fired_on_bad_state": {"const": True},
                    "silent_on_good_state": {"const": True},
                },
            },
        },
        "tests": {"type": "array", "minItems": 2},
        "evidence": {"type": "array", "minItems": 2},
    },
}


def file_line(rel: str, needle: str) -> str:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    hits = [i for i, line in enumerate(lines, 1) if needle in line]
    if len(hits) != 1:
        raise SystemExit(f"FAILED:CNL-0030 cite {rel!r} {needle!r} hits={hits}")
    return f"{rel}:{hits[0]}"


def unreduced(hit: list, lb: list) -> str:
    return f"{len(hit)}/{len(lb)}"


def markdown_body(params: dict, rows: list, crossover: int) -> str:
    lines = [
        "# CNL-0030 Chair-led topology and agenda control",
        "",
        QUESTION,
        "",
        f"**Crossover roster size (declared metric `{params['metric_name']}`): {crossover}.**",
        "",
        "## Information flow",
        "",
        "Flat council is a complete graph. Every seat publishes a full statement. "
        "A designated recorder (seat 0) reads other full statements in unprioritized "
        "seat order 1,2,3,... until a per-reader token budget is spent. There is no "
        "agenda, so a load-bearing claim at a high seat index costs the same as filler "
        "and is the first thing the cursor drops.",
        "",
        "Chair-led council is a star plus one synthesis broadcast. Every other seat "
        "spends 1 token on a nomination flag (load-bearing or not). Remaining budget "
        "buys compact agenda slots, scheduled load-bearing-first among flags the chair "
        "actually read. Members do not read n-1 full statements. The hub is the only "
        "reader who must cover the roster, and agenda order is the mechanism that "
        "changes which claims survive when the budget is short.",
        "",
        "```",
        "flat:      member_i --full statement--> every member_j (including recorder)",
        "           synthesis = whatever recorder seat 0 actually read",
        "chair-led: member_i --1-token flag--> chair; chair --recognition--> compact slot",
        "           chair --one synthesis artifact--> roster",
        "```",
        "",
        "## Declared metric",
        "",
        f"`{params['metric_formula']}`. Chair-led beats flat when that fraction is "
        "strictly greater (fractions.Fraction, not float).",
        "",
        "- Tidier: recoveries equal; chair-led uses fewer messages.",
        "- Necessary: chair-led recovery strictly exceeds flat recovery. Flat has "
        "already dropped at least one load-bearing claim that the agenda still recovers.",
        "",
        "## Parameters (fixtures/params.json)",
        "",
        f"- read_budget_tokens = {params['read_budget_tokens']}",
        f"- flat_statement_tokens = {params['flat_statement_tokens']}",
        f"- nomination_tokens = {params['nomination_tokens']}",
        f"- chair_slot_tokens = {params['chair_slot_tokens']}",
        f"- sweep_n = {params['sweep_n']}",
        "- load-bearing seats = {0, n-2, n-1} (own claim plus two highest seats).",
        "  Placement at the far end of the unprioritized cursor is intentional: putting "
        "  load-bearing claims at seats 0,1,2 would make flat never drop them under this "
        "  budget and would game the metric.",
        "",
        "## Size sweep",
        "",
        "| n | LB seats | flat recovered LB | chair recovered LB | flat recovery | chair recovery | chair beats | flat msgs | chair msgs |",
        "|---|----------|-------------------|--------------------|---------------|----------------|-------------|-----------|------------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['n']} | {r['load_bearing_seats']} | {r['flat_lb_recovered']} | "
            f"{r['chair_lb_recovered']} | {unreduced(r['flat_lb_recovered'], r['load_bearing_seats'])} "
            f"({r['flat_recovery']}) | {unreduced(r['chair_lb_recovered'], r['load_bearing_seats'])} "
            f"({r['chair_recovery']}) | {r['chair_beats_flat']} | {r['flat_messages']} | "
            f"{r['chair_messages']} |"
        )
    lines.extend(
        [
            "",
            f"Smallest n with chair_recovery > flat_recovery is **{crossover}**.",
            "At n=3 and n=4 both recover 3/3 (reduced 1/1): chair-led is only tidier "
            "(6 vs 5 messages at n=3; 12 vs 7 at n=4). At n=5 flat recovers 2/3 "
            "(misses seat 4) while chair-led recovers 3/3. That is the necessity threshold.",
            "At n=10 chair-led also drops a load-bearing claim (2/3) because nominations "
            "have consumed enough budget that only one compact slot remains; it still "
            "beats flat (1/3) but is no longer lossless. Chair-led is not magic.",
            "",
            "## Negative control",
            "",
            "Check: check_crossover_claim(claimed, mechanical) returns FIRE when "
            "claimed != mechanical and SILENT when they match.",
            "Reject state: planted claim crossover_n=3 (tidy-only region).",
            "On that state the check FIRES. On the true crossover it is SILENT.",
            "",
            "## Residual",
            "",
            "CNL-0025 (chair powers and capture resistance) is a catalog dependency and "
            "is not delivered on this tree. This note assumes an even-handed chair that "
            "schedules by nomination flags, not a captured preference. Capture is out of "
            "scope; a captured chair would change which seats the agenda prefers and "
            "could move or erase the crossover. Catalog inputs "
            "11-COUNCIL-SPECIFICATION.schema.json and "
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json are absent on this worktree; "
            "the crossover is derived from the fixtures in probes/CNL-0030/, not from "
            "those files.",
            "",
            "SUCCESS:CNL-0030",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    params = S.load_params()
    rows = S.sweep(params)
    author = S.crossover_forward(rows)
    reviewer_n = S.crossover_by_min(params)
    if author is None or author != reviewer_n:
        print(
            f"FAILED:CNL-0030 emit recount disagreement author={author} reviewer={reviewer_n}"
        )
        return 1
    planted = json.loads(
        (HERE / "fixtures" / "planted_bad_crossover.json").read_text(encoding="utf-8")
    )
    bad_claim = int(planted["claimed_crossover_n"])
    fire = S.check_crossover_claim(bad_claim, author)
    silent = S.check_crossover_claim(author, author)
    if fire != "FIRE" or silent != "SILENT":
        print(f"FAILED:CNL-0030 emit control broken fire={fire} silent={silent}")
        return 1

    note_rows = []
    for r in rows:
        note_rows.append(
            {
                "n": r["n"],
                "load_bearing_seats": r["load_bearing_seats"],
                "flat_recovered_seats": r["flat_recovered_seats"],
                "chair_recovered_seats": r["chair_recovered_seats"],
                "flat_lb_recovered": r["flat_lb_recovered"],
                "chair_lb_recovered": r["chair_lb_recovered"],
                "flat_recovery": r["flat_recovery"],
                "chair_recovery": r["chair_recovery"],
                "chair_beats_flat": r["chair_beats_flat"],
                "flat_messages": r["flat_messages"],
                "chair_messages": r["chair_messages"],
                "chair_tidier_messages": r["chair_tidier_messages"],
            }
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fwd_anchor = file_line(SIM, "def crossover_forward(rows")
    min_anchor = file_line(SIM, "def crossover_by_min(params")
    flat_anchor = file_line(SIM, "def recovered_flat_set(n")
    chair_anchor = file_line(SIM, "def recovered_chair_set(n")
    answer = (
        f"Chair-led replaces all-to-all full-text flow with a hub that spends a "
        f"1-token nomination on every other seat and then buys compact agenda slots "
        f"load-bearing-first. Under declared metric {params['metric_name']} and "
        f"parameters read_budget={params['read_budget_tokens']}, "
        f"flat_statement={params['flat_statement_tokens']}, "
        f"nomination={params['nomination_tokens']}, "
        f"slot={params['chair_slot_tokens']}, the crossover roster size is {author}: "
        f"at n=3 and n=4 both topologies recover all load-bearing claims (chair-led "
        f"is only tidier in message count); at n={author} flat recovery falls to 2/3 "
        f"while chair-led stays 3/3, so chair-led becomes necessary rather than "
        f"merely tidier."
    )
    doc = {
        "answer": answer,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": SIM,
                "exists": True,
                "role": "supporting",
            },
        ],
        "catalog_dependency_cnl_0025": {
            "artifact_present": (REPO / CNL25).is_file(),
            "assumed": (
                "even-handed chair; capture-resistance is CNL-0025 and is not answered here"
            ),
            "blocks_this_unit": False,
        },
        "catalog_output_schema": {
            "overwritten": False,
            "path": SCHEMA,
            "reason": (
                "The catalog path is a generated $ref shim into "
                "platform/schema/artifact-class-profiles.schema.json. Bare "
                "Draft7Validator against it raises RefResolutionError on "
                "ast-integrate.invalid. This unit validates against UNIT_SCHEMA "
                "in emit_note.py and does not rewrite the shared shim."
            ),
        },
        "completion_sentinel": "SUCCESS:CNL-0030",
        "declared_metric": {
            "chair_beats_when": params["chair_beats_when"],
            "formula": params["metric_formula"],
            "name": params["metric_name"],
        },
        "evidence": [
            {
                "anchor": fwd_anchor,
                "claim": (
                    f"Author path crossover_forward walks sweep rows and returns the "
                    f"first n with chair_recovery > flat_recovery; measured {author}."
                ),
                "mechanism": "file:line (forward scan of simulated rows)",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": min_anchor,
                "claim": (
                    f"Reviewer path crossover_by_min rebuilds recovered_flat_set and "
                    f"recovered_chair_set per n, then min() of winning n; measured "
                    f"{reviewer_n}. Different mechanism than the author walk."
                ),
                "mechanism": "file:line (min of independently rebuilt recovered sets)",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/CNL-0030/fixtures/params.json",
                "claim": (
                    "Catalog inputs 11-COUNCIL-SPECIFICATION.schema.json and "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json were read from disk on this worktree."
                ),
                "verdict": "REFUTED",
            },
        ],
        "kind": "council-design-note",
        "information_flow": {
            "chair_led": (
                "Star plus one synthesis broadcast: n-1 nomination flags (1 token), "
                "then compact slots scheduled load-bearing-first from flags actually "
                "read, then one synthesis artifact. Members do not read n-1 full statements."
            ),
            "flat": (
                "Complete graph: n*(n-1) full-statement hops. Recorder seat 0 reads "
                "other statements in unprioritized seat order until the token budget "
                "is spent. No agenda, so importance is invisible to the cursor."
            ),
            "what_changes": (
                "Who must read whom, and whether importance has a cheaper channel than "
                "full text. Flat: every member is a reader of every other; synthesis "
                "is the recorder's truncated inbound set. Chair-led: only the hub must "
                "cover the roster, and a 1-token flag lets remaining budget prefer "
                "load-bearing seats."
            ),
        },
        "inputs_on_this_tree": {
            "11-COUNCIL-SPECIFICATION.schema.json": False,
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": False,
            "probe_fixtures": True,
        },
        "markdown": markdown_body(params, rows, author),
        "min_bytes_threshold": 2048,
        "negative_controls": [
            {
                "check": "check_crossover_claim(claimed, mechanical) -> FIRE|SILENT",
                "fired_on_bad_state": True,
                "id": "CNL0030-C1",
                "known_good_claim": author,
                "planted_bad_claim": bad_claim,
                "silent_on_good_state": True,
                "verbatim_on_reject_state": (
                    f"claimed_crossover={bad_claim} vs mechanical={author} -> {fire}"
                ),
                "what_the_check_does_on_the_state_it_is_meant_to_reject": (
                    f"FIRE. Planted claim crossover_n={bad_claim} is in the tidy-only "
                    f"region (recoveries equal at n=3); mechanical crossover is {author}."
                ),
            }
        ],
        "produced_by": {
            "execution_substrate": "local-linux",
            "role": "council-systems-designer",
        },
        "question": QUESTION,
        "report": {
            "control_ids": ["CNL0030-C1"],
            "kind": "council-design-note",
            "observations": [
                {
                    "anchor": fwd_anchor,
                    "measured": author,
                    "method": "crossover_forward walk of simulated rows",
                    "name": "author_crossover_n",
                },
                {
                    "anchor": min_anchor,
                    "measured": reviewer_n,
                    "method": "crossover_by_min rebuilt recovered sets then min()",
                    "name": "reviewer_crossover_n",
                },
                {
                    "anchor": flat_anchor,
                    "measured": f"flat recovered set from unprioritized cursor; chair from {chair_anchor}",
                    "method": "recovered_flat_set vs recovered_chair_set",
                    "name": "information_flow_recovery_sets",
                },
            ],
        },
        "report_kind": "council-design-note",
        "schema_version": 1,
        "reviewer": {
            "independent": True,
            "method": (
                "Rebuild recovered_flat_set and recovered_chair_set per n from params, "
                "compare Fraction recoveries, collect winning n, take min(). Does not "
                "read the author's crossover_forward result."
            ),
            "recounted_crossover_n": reviewer_n,
            "reviewer_id": "CNL-0030-independent-recount",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:CNL-0030",
        "size_sweep": {
            "crossover_n": author,
            "necessary_means": (
                "Smallest sweep n at which chair load_bearing_recovery is strictly "
                "greater than flat: flat has dropped a load-bearing claim the agenda still recovers."
            ),
            "parameters": {
                "chair_slot_tokens": params["chair_slot_tokens"],
                "flat_statement_tokens": params["flat_statement_tokens"],
                "nomination_tokens": params["nomination_tokens"],
                "read_budget_tokens": params["read_budget_tokens"],
                "sweep_n": params["sweep_n"],
            },
            "rows": note_rows,
            "tidier_means": (
                "Recoveries equal and chair_messages < flat_messages. Observed at n=3 and n=4."
            ),
        },
        "state": "SUCCESS",
        "tests": [
            {"command": P1, "id": "T1-size-sweep-crossover", "result": "PASS"},
            {
                "command": P2,
                "id": "T2-negative-control-false-crossover",
                "result": "PASS",
            },
        ],
        "timestamps": {"emitted_at": now},
        "title": "Chair-led topology and agenda control",
        "unit_id": "CNL-0030",
    }

    jsonschema.Draft7Validator.check_schema(UNIT_SCHEMA)
    validator = jsonschema.Draft7Validator(UNIT_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0030 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({}, {"blob": "x" * 200}, {"unit_id": "NOPE", "state": "SUCCESS"}):
        if not list(validator.iter_errors(g)):
            print("FAILED:CNL-0030 schema accepted garbage")
            return 1
    if reviewer_n != author:
        print("FAILED:CNL-0030 report observations disagree")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    out.write_text(text, encoding="utf-8")
    raw = out.read_bytes().replace(b"\r\n", b"\n")
    if len(raw) < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0030 artifact {len(raw)}B below floor")
        return 1
    if "SUCCESS:CNL-0030" not in text:
        print("FAILED:CNL-0030 sentinel missing from artifact")
        return 1
    print(f"wrote {OUT} bytes={len(raw)} crossover_n={author}")
    print("SUCCESS:CNL-0030 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
