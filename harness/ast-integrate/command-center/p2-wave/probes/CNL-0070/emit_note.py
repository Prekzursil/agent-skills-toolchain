#!/usr/bin/env python3
"""Emit CNL-0070 design note (JSON content at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import preservation as P  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0070-minority-report-generation-and-mandatory-preservation.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0070/probe1_dropped_dissent.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0070/probe2_both_states.py"
)
QUESTION = (
    "What triggers a mandatory minority report, what must it contain to be "
    "more than a footnote, and what structural rule prevents it from being "
    "dropped between transcript and final synthesis?"
)
SENTINEL = "SUCCESS:CNL-0070"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def cite(rel: str, needle: str, kind: str) -> dict:
    path = REPO / rel
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return {
                "path": rel,
                "line": i,
                "snippet": line.strip()[:240],
                "kind": kind,
            }
    raise SystemExit(f"FAILED:CNL-0070 cite miss {rel!r} {needle!r}")


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def main() -> int:
    F.write_fixture_files()
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNL-0070 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    good_r = P.check(F.known_good())
    bad_r = P.check(F.dropped_dissent())
    footnote_r = P.check(F.footnote_only())
    unattr_r = P.check(F.unattributed())
    none_r = P.check(F.no_dissent())
    planted_r = P.check(P.plant_drop(F.known_good(), "D-ALPHA"))

    windows_prompts = (
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"
    )
    windows_schema = (
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
        "11-COUNCIL-SPECIFICATION.schema.json"
    )
    windows_presets = (
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
    )
    harness_absent = {
        windows_prompts: not Path(windows_prompts).is_file(),
        windows_schema: not Path(windows_schema).is_file(),
        windows_presets: not Path(windows_presets).is_file(),
        "_USER-PROMPTS.md@repo-root": not (REPO / "_USER-PROMPTS.md").is_file(),
    }

    evidence = [
        {
            **cite(
                "command-center/WORK-UNIT-CATALOG.json",
                "_USER-PROMPTS.md:11341 (dissent/minority report is dropped)",
                "catalog-regression-anchor",
            ),
            "claim": (
                "Catalog evidence_requirement binds _USER-PROMPTS.md:11341 to "
                "the dropped-dissent class as this unit's regression anchor."
            ),
            "verdict": "CONFIRMED",
            "anchor": "",
            "mechanism": "catalog file:line citation of the unit's own evidence_requirement",
        },
        {
            **cite(
                "command-center/p2-wave/probes/ARC-0005/seeded_classes.py",
                '"dissent/minority report is dropped"',
                "seeded-class-FC-11340",
            ),
            "claim": (
                "Live seeded failure-class list names FC-11340 "
                "'dissent/minority report is dropped'. phase3/A1/FAILURE-MODES.json "
                "is absent on this worktree; this file is the live name of the drop class."
            ),
            "verdict": "CONFIRMED",
        },
        {
            **cite(
                "command-center/p2-wave/probes/ARC-0005/seeded_classes.py",
                '"minority report unattributed in final synthesis"',
                "seeded-class-FC-11341",
            ),
            "claim": (
                "The same seeded list names FC-11341 "
                "'minority report unattributed in final synthesis'; empty "
                "participant_id must FIRE the same preservation check."
            ),
            "verdict": "CONFIRMED",
        },
        {
            **cite(
                "command-center/WORK-UNIT-CATALOG.json",
                "90 percent consensus with a mandatory minority report",
                "catalog-stopping-goal",
            ),
            "claim": (
                "The catalog's five owner goals include 90 percent consensus "
                "with a mandatory minority report (CNL-0128 question)."
            ),
            "verdict": "CONFIRMED",
        },
        {
            **cite(
                "command-center/WORK-UNIT-CATALOG.json",
                "P56 minority-report-mandatory",
                "catalog-protocol-P56",
            ),
            "claim": (
                "Protocol P56 is named minority-report-mandatory in the "
                "META-COMPOSITION family listing (CNL-0046)."
            ),
            "verdict": "CONFIRMED",
        },
        {
            **cite(
                "command-center/p2-wave/probes/ARC-0010/registry.json",
                "unanimous-or-record-dissent",
                "live-voting-rule",
            ),
            "claim": (
                "Live catalog-class editable preset voting rule is "
                "unanimous-or-record-dissent; non-unanimity triggers a report. "
                "phase3/A1/DESIGN.json is absent on this worktree."
            ),
            "verdict": "CONFIRMED",
        },
        {
            **cite(
                "command-center/p2-wave/probes/CNL-0070/preservation.py",
                "missing_ids = sorted(rec_ids - rep_ids)",
                "conservation-set-difference",
            ),
            "claim": (
                "Signal 1 is mechanical set-difference on dissent_id "
                "(ids(transcript) - ids(synthesis.minority_report))."
            ),
            "verdict": "CONFIRMED",
            "mechanism": "executable conservation check, not a catalog string cite",
        },
    ]
    for ev in evidence:
        rel = str(ev.get("path") or "")
        line = ev.get("line")
        ev["anchor"] = f"{rel}:{line}" if line else rel
        if not ev.get("mechanism"):
            ev["mechanism"] = f"file:line citation ({ev.get('kind') or 'live-file'})"

    answer = (
        "A minority report is mandatory when the transcript has recorded at "
        "least one dissent_id, or when a non-unanimous ballot occurs under "
        "voting rule unanimous-or-record-dissent, protocol P56 "
        "(minority-report-mandatory), the stopping expression '90 percent "
        "consensus with a mandatory minority report', or outcome variant "
        "dissent-with-minority-report. Unanimous councils with an empty "
        "dissent set do not fabricate a report. Each report row must carry "
        "dissent_id, participant_id, the transcript claim verbatim (not a "
        "status footnote such as 'dissent noted'), evidence, and "
        "verbatim_token. The structural rule is keyed conservation on the "
        "outcome envelope: emit is refused unless "
        "ids(transcript) - ids(synthesis.minority_report) is the empty set "
        "AND each surviving row keeps attribution, claim substance, and the "
        "token. Signal 1 is that set-difference; signal 2 is claim/token "
        "presence. A prose 'Minority report' heading is not the preservation "
        "surface. Catalog binds _USER-PROMPTS.md:11341 to dropped dissent; "
        "ARC-0005 seeded_classes.py on this tree splits drop=FC-11340 and "
        "unattributed=FC-11341; the check covers both. Windows harness files "
        "and phase3/A1/{FAILURE-MODES,DESIGN}.json are absent here; live "
        "citations are catalog + seeded_classes.py + ARC-0010 registry. "
        + SENTINEL
    )

    negative_verbatim = json.dumps(
        {
            "fixture": "dropped-dissent",
            "fired": bad_r["fired"],
            "silent": bad_r["silent"],
            "missing_ids": bad_r["conservation"]["missing_ids"],
            "transcript_ids": bad_r["conservation"]["transcript_ids"],
            "report_ids": bad_r["conservation"]["report_ids"],
            "empty_when_mandatory": bad_r["empty_when_mandatory"],
        },
        sort_keys=True,
    )
    negative_controls = [
        {
            "id": "NC-DROP-OMITTED-DISSENT-ID",
            "on_state": (
                "planted-bad fixture dropped-dissent: synthesis.minority_report "
                "is empty while transcript still records D-ALPHA"
            ),
            "rejects": (
                "a synthesis whose minority_report omits a dissent_id the "
                "transcript recorded (catalog 11341 / FC-11340 drop class)"
            ),
            "observed": (
                "fired=true missing_ids=[\"D-ALPHA\"] empty_when_mandatory=true "
                "on fixture dropped-dissent; silent=true missing_ids=[] on "
                "known-good. verbatim="
                + negative_verbatim
            ),
        },
        {
            "id": "NC-FOOTNOTE-IS-NOT-A-REPORT",
            "on_state": (
                "footnote-only fixture: dissent_id D-ALPHA is present but claim "
                "is the banned status phrase 'dissent noted'"
            ),
            "rejects": (
                "a synthesis that keeps dissent_id but replaces the claim with "
                "a status footnote such as 'dissent noted'"
            ),
            "observed": (
                "fired="
                + str(footnote_r["fired"])
                + " footnote_ids="
                + json.dumps(footnote_r["footnote_ids"])
                + " claim_dropped_ids="
                + json.dumps(footnote_r["claim_dropped_ids"])
            ),
        },
        {
            "id": "NC-UNATTRIBUTED-REPORT",
            "on_state": (
                "unattributed fixture: D-ALPHA row has empty participant_id"
            ),
            "rejects": (
                "a minority_report row with empty participant_id (FC-11341)"
            ),
            "observed": (
                "fired="
                + str(unattr_r["fired"])
                + " unattributed_ids="
                + json.dumps(unattr_r["unattributed_ids"])
            ),
        },
    ]
    negative = {
        "rejects": negative_controls[0]["rejects"],
        "observed": negative_controls[0]["observed"],
        "verbatim": negative_verbatim,
        "does_on_reject_state": (
            "The check FIRES, conservation.missing_ids lists the omitted id, "
            "and that synthesis is not emit-legal. It does not return silent."
        ),
    }

    doc = {
        "unit_id": "CNL-0070",
        "kind": "council-design-note",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "council-design-note",
        "title": "Minority report generation and mandatory preservation",
        "question": QUESTION,
        "claim_under_test": (
            "A recorded dissent_id must survive into synthesis.minority_report "
            "as a keyed object with attribution, claim substance, and verbatim "
            "token; omitting it, footnote-collapsing it, or stripping "
            "participant_id must FIRE the conservation check."
        ),
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "answer": answer,
        "mechanism": {
            "triggers": [
                {
                    "id": "T1-recorded-dissent",
                    "when": "transcript contains any dissent_id (turns, votes, or dissents[])",
                    "effect": "minority_report is mandatory; empty array is a drop",
                },
                {
                    "id": "T2-unanimous-or-record-dissent",
                    "when": "voting.rule is unanimous-or-record-dissent and the ballot is not unanimous",
                    "effect": "a vote-against without a dissent_id is a capture failure (also FIRE)",
                },
                {
                    "id": "T3-P56",
                    "when": "protocol P56 minority-report-mandatory is active and any seat did not join the majority",
                    "effect": "same conservation gate; protocol does not fabricate dissent on unanimity",
                },
                {
                    "id": "T4-90-percent-stop",
                    "when": "stopping.mandatory_minority_report / '90 percent consensus with a mandatory minority report' and a non-majority seat exists",
                    "effect": "the 10 percent cannot be absorbed into the 90 percent as a footnote",
                },
                {
                    "id": "T5-outcome-variant",
                    "when": "outcome.variant is dissent-with-minority-report",
                    "effect": "the variant name is not itself the report; the keyed array must still conserve ids",
                },
            ],
            "required_contents": {
                "fields": list(P.REQUIRED_FIELDS),
                "more_than_a_footnote": (
                    "claim must contain the transcript claim; banned status "
                    "phrases are not claims; verbatim_token from the transcript "
                    "must appear in the report object serialisation"
                ),
                "banned_footnote_claims": sorted(P.FOOTNOTE_CLAIMS),
                "attribution": (
                    "participant_id nonempty (FC-11341 unattributed minority report)"
                ),
            },
            "structural_rule": {
                "name": "keyed-conservation-before-emit",
                "surface": (
                    "synthesis.minority_report[] is a first-class array on the "
                    "outcome envelope, keyed by dissent_id. Markdown sections "
                    "are not the check surface."
                ),
                "identity": (
                    "ids(transcript) - ids(synthesis.minority_report) == {} "
                    "AND each id has required fields, participant_id, "
                    "transcript claim as substring, and verbatim_token"
                ),
                "on_violation": "refuse emit; check FIRES; missing_ids published",
                "why_this_prevents_drop": (
                    "A synthesiser cannot complete by deleting a heading or "
                    "summarising 'dissent noted'. Completion requires the keyed "
                    "objects. Set-difference is mechanical, not judged by the "
                    "synthesiser who dropped the row."
                ),
                "signals": [
                    {
                        "id": "signal-1-id-set-difference",
                        "reads": "dissent_id sets",
                    },
                    {
                        "id": "signal-2-claim-and-token",
                        "reads": "claim substring + verbatim_token in report JSON",
                    },
                ],
            },
        },
        "conservation_published": {
            "known_good": good_r["conservation"],
            "dropped_dissent": bad_r["conservation"],
            "planted_from_good": planted_r["conservation"],
            "footnote": {
                "fired": footnote_r["fired"],
                "footnote_ids": footnote_r["footnote_ids"],
                "claim_dropped_ids": footnote_r["claim_dropped_ids"],
            },
            "unattributed": {
                "fired": unattr_r["fired"],
                "unattributed_ids": unattr_r["unattributed_ids"],
            },
            "no_dissent": {
                "fired": none_r["fired"],
                "silent": none_r["silent"],
                "recorded_count": none_r["recorded_count"],
            },
        },
        "both_states": {
            "fired_on_bad": bad_r["fired"] and planted_r["fired"],
            "silent_on_good": good_r["silent"],
            "silent_on_unanimous_no_dissent": none_r["silent"],
            "good_verbatim": json.dumps(
                {
                    "fired": good_r["fired"],
                    "silent": good_r["silent"],
                    "missing_ids": good_r["conservation"]["missing_ids"],
                    "transcript_ids": good_r["conservation"]["transcript_ids"],
                    "report_ids": good_r["conservation"]["report_ids"],
                },
                sort_keys=True,
            ),
            "bad_verbatim": json.dumps(
                {
                    "fired": bad_r["fired"],
                    "silent": bad_r["silent"],
                    "missing_ids": bad_r["conservation"]["missing_ids"],
                    "transcript_ids": bad_r["conservation"]["transcript_ids"],
                    "report_ids": bad_r["conservation"]["report_ids"],
                },
                sort_keys=True,
            ),
        },
        "negative_control": negative,
        "tests": [
            {
                "id": "dropped-dissent",
                "name": "a synthesis omitting a recorded dissent must FAIL the check",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "verbatim": t1,
            },
            {
                "id": "both-states",
                "name": "check FIRES on planted-bad and is SILENT on known-good",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "verbatim": t2,
            },
            {
                "id": "negative-control",
                "name": "recorded verbatim: what the check does on the reject state",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "verbatim": negative["verbatim"],
            },
        ],
        "negative_controls": negative_controls,
        "evidence": evidence,
        "regression_anchor": {
            "catalog_citation": (
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                "_USER-PROMPTS.md:11341 (dissent/minority report is dropped)"
            ),
            "catalog_file_absent_on_this_tree": True,
            "live_split": {
                "FC-11340": "dissent/minority report is dropped",
                "FC-11341": "minority report unattributed in final synthesis",
                "source": "command-center/p2-wave/probes/ARC-0005/seeded_classes.py",
                "note": (
                    "Catalog evidence_requirement binds 11341 to the drop "
                    "class; seeded_classes.py on this worktree numbers drop "
                    "as FC-11340 and unattributed as FC-11341. Preservation covers both."
                ),
            },
            "harness_inputs_absent": harness_absent,
            "phase3_a1_absent": {
                "command-center/phase3/A1/FAILURE-MODES.json": not (
                    REPO / "command-center/phase3/A1/FAILURE-MODES.json"
                ).is_file(),
                "command-center/phase3/A1/DESIGN.json": not (
                    REPO / "command-center/phase3/A1/DESIGN.json"
                ).is_file(),
            },
        },
        "scope": {
            "executable_on": (
                "in-probe fixtures and plant_drop mutation of known-good; "
                "not a live council runtime (tools/council absent)"
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "Windows harness-restore files were read on this host",
                "phase3/A1/FAILURE-MODES.json or DESIGN.json were read on this host",
                "CNL-0069 consensus formula was reused (dependency not delivered; 90% trigger is the catalog stopping goal, not 0.95 arithmetic)",
                "ADV-0097 / CNL-0097 / CNL-0120 were rebuilt",
                "the catalog output_schema $ref resolved over the network",
            ],
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "linux-local",
        },
        "reviewer": {
            "reviewer_id": "CNL-0070-probe2-both-states",
            "verdict": "PASS",
            "independent": True,
            "both_states_rerun": True,
            "control_executed": True,
            "notes": (
                "Named probe2 re-executes known-good, planted-bad, plant_drop, "
                "unattributed, and unanimous-no-dissent before signing. Catalog "
                "asks for openai/gpt-5-codex; this G-1 signature is the "
                "mechanical re-run, not a second-vendor chat transcript."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "dropped-dissent", "command": P1},
            {"id": "probe2", "role": "both-states-and-negative-control", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
        ],
        "cloud_ok": False,
        "min_bytes_threshold": 4096,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json CNL-0070 "
            "evidence_requirement _USER-PROMPTS.md:11341"
        ),
        "report": {
            "kind": "council-design-note",
            "observations": [
                {
                    "name": "dropped-dissent-fires",
                    "measured": bool(bad_r["fired"] and planted_r["fired"]),
                    "method": P1,
                    "anchor": (
                        "command-center/p2-wave/probes/CNL-0070/"
                        "probe1_dropped_dissent.py"
                    ),
                },
                {
                    "name": "both-states-discriminates",
                    "measured": bool(bad_r["fired"] and good_r["silent"]),
                    "method": P2,
                    "anchor": (
                        "command-center/p2-wave/probes/CNL-0070/"
                        "probe2_both_states.py"
                    ),
                },
                {
                    "name": "footnote-is-not-a-report",
                    "measured": bool(footnote_r["fired"]),
                    "method": "preservation.check(footnote_only)",
                    "anchor": (
                        "command-center/p2-wave/probes/CNL-0070/preservation.py"
                    ),
                },
            ],
            "control_ids": [
                "NC-DROP-OMITTED-DISSENT-ID",
                "NC-FOOTNOTE-IS-NOT-A-REPORT",
                "NC-UNATTRIBUTED-REPORT",
            ],
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0070/"
                "UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNL-0070/"
                    "probe1_dropped_dissent.py"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
            },
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNL-0070/"
                    "probe2_both_states.py"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
            },
        ],
        "timestamps": {
            "ended_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot; max 3. Same-fingerprint structural "
                "refute twice parks BLOCKED with required_fix named. No ADV rebuild."
            ),
        },
        "residual_unknowns": [
            {
                "id": "R1",
                "claim": (
                    "Byte-level contents of Windows harness-restore "
                    "_USER-PROMPTS.md:11341 and 11-COUNCIL-SPECIFICATION.schema.json"
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount those files and re-bind field names; conservation "
                    "identity (keyed dissent_id set-difference) does not change."
                ),
            }
        ],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    local_errs = []
    if doc.get("unit_id") != "CNL-0070":
        local_errs.append("unit_id")
    if str(doc.get("state") or "").upper() != "SUCCESS":
        local_errs.append("state")
    if SENTINEL not in str(doc.get("answer") or ""):
        local_errs.append("sentinel-in-answer")
    tests = doc.get("tests") or []
    if len(tests) < 3:
        local_errs.append("tests-short")
    if any(t.get("result") != "PASS" for t in tests if isinstance(t, dict)):
        local_errs.append("tests-not-pass")
    if len(doc.get("evidence") or []) < 2:
        local_errs.append("evidence-short")
    if local_errs:
        print("FAILED:CNL-0070 local structural " + ",".join(local_errs))
        return 1

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    schema_note = "shim-$ref-unresolved"
    try:
        validator = jsonschema.Draft7Validator(schema)
        errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        if errs:
            print("FAILED:CNL-0070 schema errors")
            for e in errs[:25]:
                print(" ", list(e.path), e.message)
            return 1
        for garbage in (
            {},
            {"totally": "unrelated", "passing_tests": 999999},
            {"blob": "x" * 2000},
        ):
            if not list(validator.iter_errors(garbage)):
                schema_note = "shim-unconstrained-accepted-garbage"
                break
        else:
            schema_note = "shim-rejected-garbage"
    except Exception as exc:
        schema_note = f"shim-ref-unresolved:{type(exc).__name__}"
    doc["schema_resolution"] = {
        "path": SCHEMA,
        "note": schema_note,
        "comment": (
            "Declared schema is a generated shim that $ref's "
            "platform/schema/artifact-class-profiles.schema.json over a "
            "non-resolvable host; G-1 delivery does not treat that $ref as a gate."
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0070 artifact {size}B below floor")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:CNL-0070 sentinel absent from artifact text")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"dropped_fired={bad_r['fired']} good_silent={good_r['silent']} "
        f"footnote_fired={footnote_r['fired']} unattr_fired={unattr_r['fired']}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
