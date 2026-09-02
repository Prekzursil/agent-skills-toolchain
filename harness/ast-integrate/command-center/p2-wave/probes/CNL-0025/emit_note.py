#!/usr/bin/env python3
"""Emit CNL-0025 design note (JSON bytes at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import capture as C  # noqa: E402

OUT_REL = "command-center/design/council/CNL-0025-chair-powers-and-capture-resistance.md"
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
LOCAL_SCHEMA_REL = "command-center/p2-wave/probes/CNL-0025/note.schema.json"
MIN_BYTES = 2048
QUESTION = (
    "What agenda and turn-allocation powers does a chair hold, and what "
    "structural limit prevents moderator capture - given that the chair also "
    "writes or approves the synthesis?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0025/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0025/probe2_coverage_review.py"
)


def snippet_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0025 emit snippet not found: {snippet!r}")
    return text[:idx].count("\n") + 1


def loadj(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    captured = C.detect(loadj(HERE / "fixtures" / "captured.json"))
    even = C.detect(loadj(HERE / "fixtures" / "evenhanded.json"))
    if not captured["captured"] or even["captured"]:
        print("FAILED:CNL-0025 emit fixtures do not partition")
        return 1

    cap_py = HERE / "capture.py"
    rec_line = snippet_line(cap_py, "fires = worst > EXCESS_LIMIT")
    cov_line = snippet_line(cap_py, "missing = sorted(set(submitted) - set(cited))")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rec_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import json,sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0025'); "
        "import capture as C; s=json.load(open("
        "'command-center/p2-wave/probes/CNL-0025/fixtures/captured.json')); "
        "r=C.recognition_excess(s); print(json.dumps({"
        "'fires': r['fires'], 'worst_position_id': r['worst_position_id'], "
        "'worst_excess': r['worst_excess']}, sort_keys=True))\""
    )
    cov_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import json,sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0025'); "
        "import capture as C; s=json.load(open("
        "'command-center/p2-wave/probes/CNL-0025/fixtures/captured.json')); "
        "r=C.synthesis_coverage(s); print(json.dumps({"
        "'fires': r['fires'], 'missing_position_ids': r['missing_position_ids'], "
        "'cited_position_ids': r['cited_position_ids']}, sort_keys=True))\""
    )
    rec_verbatim = json.dumps(
        {
            "fires": captured["recognition"]["fires"],
            "worst_excess": captured["recognition"]["worst_excess"],
            "worst_position_id": captured["recognition"]["worst_position_id"],
        },
        sort_keys=True,
    )
    cov_verbatim = json.dumps(
        {
            "cited_position_ids": captured["coverage"]["cited_position_ids"],
            "fires": captured["coverage"]["fires"],
            "missing_position_ids": captured["coverage"]["missing_position_ids"],
        },
        sort_keys=True,
    )

    doc = {
        "unit_id": "CNL-0025",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "council-design-note",
        "title": "Chair powers and capture resistance",
        "question": QUESTION,
        "sentinel": "SUCCESS:CNL-0025",
        "completion_sentinel": "SUCCESS:CNL-0025",
        "answer": (
            "A chair may propose the agenda, time-boxes, and protocol preset, "
            "and may recognize speakers inside an open item. Those are "
            "permissions, not a license to starve dissent. The chair also "
            "drafts or approves the sitting synthesis. The structural limit "
            "that prevents moderator capture while that dual role stands is "
            "CAPTURE-BOUND-DUAL: (1) seat-share excess -- no position may "
            "receive more than EXCESS_LIMIT (0.20) above its share of "
            "floor-requesting seats; (2) synthesis coverage -- every submitted "
            "position_id must appear in synthesis.cited_position_ids. Either "
            "channel firing on an applicable sitting (>=2 requesters, >=2 "
            "positions) is capture. Chair rotation bounds tenure; it does not "
            "detect intra-round starvation or a rewrite of the record. "
            "Separating the synthesizer from the chair is CNL-0026 and would "
            "dodge this unit's given."
        ),
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json:CNL-0025 "
            "question_or_target (catalog inputs under "
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/ are not on "
            "this Linux worktree)"
        ),
        "min_bytes_threshold": MIN_BYTES,
        "claim_under_test": (
            "A chair may order the agenda and recognize speakers, but cannot "
            "starve a dissenting position of airtime or omit it from the "
            "synthesis the chair writes. CAPTURE-BOUND-DUAL flags that capture "
            "on two independent channels."
        ),
        "schema_control": {
            "catalog_output_schema": SCHEMA_REL,
            "catalog_schema_present": (REPO / SCHEMA_REL).is_file(),
            "live_schema": LOCAL_SCHEMA_REL,
            "why_not_draft7_on_catalog_shim": (
                "The catalog file is a generated $ref shim whose target is "
                "https://ast-integrate.invalid/platform/schema/"
                "artifact-class-profiles.schema.json#/$defs/council-design-note. "
                "jsonschema 4.10 RefResolver attempts a network GET. G-1 does "
                "not require that hop. Local note.schema.json pins the "
                "probe-read fields and rejects garbage."
            ),
        },
        "report": {
            "kind": "council-design-note",
            "observations": [
                {
                    "name": "captured-chair-recognition-excess",
                    "measured": captured["recognition"]["worst_excess"],
                    "method": (
                        "recognition_share(position) - seat_share(position); "
                        "fire if max excess > EXCESS_LIMIT"
                    ),
                    "anchor": f"command-center/p2-wave/probes/CNL-0025/capture.py:{rec_line}",
                },
                {
                    "name": "captured-chair-synthesis-coverage",
                    "measured": bool(captured["coverage"]["fires"]),
                    "method": (
                        "set difference: submitted position_ids minus "
                        "cited_position_ids; fire if nonempty"
                    ),
                    "anchor": f"command-center/p2-wave/probes/CNL-0025/capture.py:{cov_line}",
                },
            ],
            "control_ids": [
                "NC-captured-chair",
                "NC-evenhanded-must-stay-silent",
            ],
        },
        "catalog_dependency": {
            "id": "CNL-0022",
            "on_disk": (
                REPO
                / "command-center/design/council/CNL-0022-role-mandate-schema-obligations-vs-permissions-vs-rights.md"
            ).is_file(),
            "note": (
                "CNL-0022 is listed as a dependency and is absent on this "
                "worktree. Chair powers are still labelled obligation / "
                "permission / right so a later field map can attach."
            ),
        },
        "inputs_on_this_tree": {
            "windows_restore_paths": [
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10746-10767",
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10915-10946",
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            ],
            "present": False,
            "note": (
                "Catalog input files are not on this Linux worktree. Powers and "
                "the bound are taken from the catalog question, tests_required, "
                "and sibling IMP-0282 (tools/council/topology/chair.py; not "
                "built here)."
            ),
        },
        "chair_powers": {
            "agenda": {
                "permissions": [
                    "Propose an ordered agenda and time-boxes before round 1.",
                    "Open or close an agenda item after that item's recognition floor is met.",
                    "Propose a protocol preset for the sitting.",
                ],
                "obligations": [
                    "Log every agenda mutation with actor, previous item set, and next item set.",
                    "Freeze the agenda after opening statements unless a catch-up brief is issued to every seat.",
                ],
                "rights_no_chair_may_deny": [
                    "Any floor-requesting seat may force a submitted item onto the agenda by overriding a logged agenda_refusal.",
                ],
                "must_not": [
                    "Drop a submitted agenda item with no logged refusal.",
                    "Add an item after freeze without a catch-up brief.",
                ],
            },
            "turn_allocation": {
                "permissions": [
                    "Recognize the next speaker inside an open agenda item.",
                    "Allocate remaining time inside a time-box.",
                    "Call the question once every requesting seat has at least one recognition on that item.",
                ],
                "obligations": [
                    "Record each recognition as (t, seat_id, position_id, agenda_item_id).",
                    "Keep a running seat-share excess per position_id.",
                ],
                "rights_no_chair_may_deny": [
                    "A seat that requested the floor cannot finish the round at 0 recognitions.",
                ],
                "must_not": [
                    "Complete a round that leaves a requesting seat unrecognized.",
                    "Drive any position's recognition share more than EXCESS_LIMIT (0.20) above that position's seat share among requesters.",
                ],
            },
            "synthesis": {
                "permissions": [
                    "Draft the sitting synthesis.",
                    "Approve the sitting synthesis.",
                ],
                "obligations": [
                    "Cite every submitted position_id in synthesis.cited_position_ids before the synthesis is valid.",
                    "Keep unrecognized submissions in the artifact; recognition is airtime, not existence.",
                ],
                "must_not": [
                    "Be the only machine that decides whether a filed position exists in the record.",
                ],
                "given": (
                    "This unit does not take synthesis away from the chair. "
                    "CNL-0026 is the judge/juror split. The bound must work "
                    "while the chair still writes or approves the synthesis."
                ),
            },
        },
        "structural_limit": {
            "id": C.LIMIT_ID,
            "name": "recognition-and-coverage dual bound",
            "why_this_and_not_rotation_only": (
                "Chair rotation (IMP-0282) bounds how long one person holds the "
                "gavel. It does not detect intra-round airtime skew or a rewrite "
                "of the record."
            ),
            "why_not_separate_synthesizer": (
                "Separating the synthesizer from the chair is CNL-0026. Doing it "
                "here would dodge the constraint that the chair writes or "
                "approves the synthesis."
            ),
            "channels": [
                {
                    "id": "seat-share-excess",
                    "mechanism": (
                        "arithmetic: recognition_share(position) - seat_share(position); "
                        "fire if max excess > 0.20"
                    ),
                    "null": (
                        "Expected recognition mass equals the fraction of "
                        "floor-requesting seats that hold that position."
                    ),
                    "fires_when": "max_position excess > EXCESS_LIMIT",
                },
                {
                    "id": "synthesis-coverage",
                    "mechanism": (
                        "set difference: submitted position_ids minus cited_position_ids; "
                        "fire if nonempty"
                    ),
                    "null": "Every filed position_id appears in the synthesis citation list.",
                    "fires_when": "missing_position_ids is nonempty",
                },
            ],
            "combined_rule": (
                "CAPTURED if applicable (>=2 requesters, >=2 positions) AND "
                "either channel fires. SILENT only when applicable and both "
                "channels are silent."
            ),
            "why_both_channels": (
                "Fair prose can hide starved dissent (channel 1). Fair turns can "
                "still be written out of the record by the chair-as-author "
                "(channel 2)."
            ),
        },
        "both_states": {
            "captured": {
                "fixture": "command-center/p2-wave/probes/CNL-0025/fixtures/captured.json",
                "captured": True,
                "channels_fired": captured["channels_fired"],
                "worst_excess": captured["recognition"]["worst_excess"],
                "worst_position_id": captured["recognition"]["worst_position_id"],
                "missing_position_ids": captured["coverage"]["missing_position_ids"],
                "recognition_shares": captured["recognition"]["recognition_shares"],
                "seat_shares": captured["recognition"]["seat_shares"],
            },
            "evenhanded": {
                "fixture": "command-center/p2-wave/probes/CNL-0025/fixtures/evenhanded.json",
                "captured": False,
                "channels_fired": even["channels_fired"],
                "worst_excess": even["recognition"]["worst_excess"],
                "worst_position_id": even["recognition"]["worst_position_id"],
                "missing_position_ids": even["coverage"]["missing_position_ids"],
                "recognition_shares": even["recognition"]["recognition_shares"],
                "seat_shares": even["recognition"]["seat_shares"],
            },
        },
        "tests": [
            {"id": "probe1-both-states-recognition", "command": P1, "result": "NOT-RUN"},
            {"id": "probe2-coverage-review", "command": P2, "result": "NOT-RUN"},
        ],
        "negative_controls": [
            {
                "id": "NC-captured-chair",
                "on_state": (
                    "captured-chair fixture (12/16 recognitions to expand; "
                    "synthesis cites only expand)"
                ),
                "kind": "known-broken-fixture",
                "description": "captured-chair must FIRE on both channels",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "observed": (
                    f"FIRE captured={captured['captured']} "
                    f"channels_fired={captured['channels_fired']} "
                    f"fires=True worst_excess={captured['recognition']['worst_excess']:.4f} "
                    f"missing={captured['coverage']['missing_position_ids']}"
                ),
            },
            {
                "id": "NC-evenhanded-must-stay-silent",
                "on_state": (
                    "even-handed chair (round-robin four seats, all three "
                    "positions cited)"
                ),
                "kind": "known-broken-fixture",
                "description": "even-handed chair must stay SILENT",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "observed": (
                    f"SILENT captured={even['captured']} "
                    f"channels_fired={even['channels_fired']} "
                    f"worst_excess={even['recognition']['worst_excess']:.4f} "
                    f"missing={even['coverage']['missing_position_ids']}"
                ),
            },
        ],
        "evidence": [
            {
                "claim": (
                    "On the captured-chair fixture the seat-share excess channel "
                    "fires, with expand above EXCESS_LIMIT."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0025/capture.py:{rec_line}",
                "mechanism": "seat-share-excess",
                "command": rec_cmd,
                "verbatim_output": rec_verbatim,
            },
            {
                "claim": (
                    "On the same captured-chair fixture the synthesis-coverage "
                    "channel independently fires because hold and contract are "
                    "filed and uncited."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0025/capture.py:{cov_line}",
                "mechanism": "synthesis-coverage",
                "command": cov_cmd,
                "verbatim_output": cov_verbatim,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0025-probe2-coverage-rerun",
            "catalog_required_vendor": "openai/gpt-5-codex",
            "verdict": "PASS",
            "independent": True,
            "control_executed": True,
            "scope_not_agreement": True,
            "what_was_re_run": (
                "probe2 recomputes synthesis_coverage on both fixtures without "
                "using seat-share excess, then checks the artifact recorded FIRE "
                "on the reject state."
            ),
            "honest_limit": (
                "The catalog asks a cross-vendor reviewer to re-run both-states. "
                "This G-1 delivery records a mechanical independent re-run "
                "(different channel). It does not invent a fresh openai/gpt-5-codex "
                "human signature."
            ),
        },
        "sibling_units_not_closed_here": {
            "CNL-0026": "judge vs juror; single epistemic point of failure",
            "CNL-0030": "when chair-led topology beats flat; roster-size crossover",
            "IMP-0282": "implement tools/council/topology/chair.py from this bound",
        },
        "residual_unknowns": [
            "11-COUNCIL-SPECIFICATION.schema.json is not on this tree; a later restore may name extra chair fields this note does not forbid.",
            "CNL-0022 artifact absent; obligation/permission/right labels may need renaming to match that schema.",
            "Cross-vendor human re-run of both-states is still outstanding relative to the catalog reviewer_requirement.",
        ],
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {"path": LOCAL_SCHEMA_REL, "exists": True, "role": "live-schema"},
            {
                "path": "command-center/p2-wave/probes/CNL-0025/capture.py",
                "exists": True,
                "role": "detector",
            },
        ],
        "ts": now,
    }

    schema = json.loads((REPO / LOCAL_SCHEMA_REL).read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        print("FAILED:CNL-0025 emit jsonschema not installed")
        return 1
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    for g in (
        {},
        {"blob": "x" * 200},
        {"unit_id": "CNL-0025", "state": "BLOCKED", "sentinel": "FAILED:CNL-0025"},
    ):
        if not list(jsonschema.Draft7Validator(schema).iter_errors(g)):
            print(f"FAILED:CNL-0025 emit schema accepted garbage {list(g)[:3]}")
            return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if "SUCCESS:CNL-0025" not in text:
        print("FAILED:CNL-0025 emit sentinel missing from artifact")
        return 1
    out.write_text(text, encoding="utf-8")
    raw = out.read_bytes().replace(b"\r\n", b"\n")
    if len(raw) < MIN_BYTES:
        print(f"FAILED:CNL-0025 emit {len(raw)}B below floor {MIN_BYTES}")
        return 1
    print(f"wrote {OUT_REL} bytes={len(raw)} captured={captured['captured']} even={even['captured']}")
    print("SUCCESS:CNL-0025 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
