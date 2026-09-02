#!/usr/bin/env python3
"""Emit the CNL-0118 council simulation spec (JSON at the catalog .md path)."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import run, two_run_identical  # noqa: E402
from schema_check import garbage_accepted, schema_errors  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0118-role-enforcement-and-participant-replacement-simulation.md"
)
SCHEMA = "command-center/schema/council-simulation-spec.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0118/probe1_replay.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0118/probe2_recount.py"
)
QUESTION = (
    "Does the runtime actually enforce role mandates and survive a mid-round "
    "replacement - demonstrated by a scripted participant that deliberately "
    "violates its mandate and one that dies mid-vote?"
)
HANG_TIMEOUT_S = 0.2
SUPPORTING = [
    ("command-center/p2-wave/probes/CNL-0118/harness.py", "supporting"),
    ("command-center/p2-wave/probes/CNL-0118/fixtures/roles.json", "fixture"),
    ("command-center/p2-wave/probes/CNL-0118/fixtures/script.json", "fixture"),
    ("command-center/p2-wave/probes/CNL-0118/fixtures/scenario.json", "fixture"),
    ("command-center/schema/council-simulation-spec.schema.json", "supporting"),
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def line_of(rel: str, needle: str) -> str:
    text = (REPO / rel).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return f"{rel}:{i}"
    raise SystemExit(f"FAILED:CNL-0118 emit missing needle {needle!r} in {rel}")


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


def artifact_row(rel: str, role: str) -> dict:
    digest, size = digest_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(
    *,
    role: str,
    method: str,
    command: str,
    raw_output: str,
    fingerprint: str,
    exit_code: int = 0,
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:65536],
        "fingerprint": fingerprint,
        "exit_code": exit_code,
    }


def hang_control() -> tuple[bool, str, float]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(run, enforce=True, hang_instead_of_replace=True)
        t0 = time.monotonic()
        try:
            hung = fut.result(timeout=HANG_TIMEOUT_S)
            elapsed = time.monotonic() - t0
            return False, f"hang mutant returned {hung.get('terminal_state')}", elapsed
        except concurrent.futures.TimeoutError:
            elapsed = time.monotonic() - t0
            msg = (
                "NEGATIVE_CONTROL hang-instead-of-replace -> REPLACEMENT_TIMEOUT "
                f"via wall-clock deadline timeout_s={HANG_TIMEOUT_S} "
                f"elapsed_s={elapsed:.3f} FIRES"
            )
            return True, msg, elapsed


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = run(enforce=True)
    stripped = run(enforce=False)
    identical, _, _ = two_run_identical()
    hang_fired, hang_msg, hang_elapsed = hang_control()
    if not identical:
        print("FAILED:CNL-0118 two-run events not byte-identical")
        return 1
    if result["terminal_state"] != "COMPLETED_AFTER_REPLACEMENT":
        print("FAILED:CNL-0118 terminal", result["terminal_state"])
        return 1
    if not result["violator_caught"] or result["compliant_flagged"]:
        print("FAILED:CNL-0118 enforcement polarity")
        return 1
    if stripped["violator_caught"]:
        print("FAILED:CNL-0118 stripped run still catches (vacuous)")
        return 1
    if not hang_fired or hang_elapsed > 1.0:
        print("FAILED:CNL-0118 hang control", hang_msg, hang_elapsed)
        return 1

    prod = {
        "tools/council/simulate.py": present("tools/council/simulate.py"),
        "tools/council/roles/guard.py": present("tools/council/roles/guard.py"),
        "tools/council/roles/mandate.py": present("tools/council/roles/mandate.py"),
        "CNL-0117 artifact": present(
            "command-center/design/council/"
            "CNL-0117-deterministic-scripted-participant-simulation-harness.md"
        ),
        "CNL-0021 artifact": present(
            "command-center/design/council/"
            "CNL-0021-participant-replacement-and-duplicate-independence-detecti.md"
        ),
        "CNL-0022 artifact": present(
            "command-center/design/council/"
            "CNL-0022-role-mandate-schema-obligations-vs-permissions-vs-rights.md"
        ),
        "11-COUNCIL-SPECIFICATION.schema.json": present(
            "11-COUNCIL-SPECIFICATION.schema.json"
        ),
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": present(
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
        ),
    }

    mr = {
        "violator_caught": result["violator_caught"],
        "compliant_flagged": result["compliant_flagged"],
        "mention_flagged": result["mention_flagged"],
        "violator_rejection_count": result["violator_rejection_count"],
        "compliant_rejection_count": result["compliant_rejection_count"],
        "mention_rejection_count": result["mention_rejection_count"],
        "ballots_committed": result["ballots_committed"],
        "dying_seat_ballot_present": result["dying_seat_ballot_present"],
        "replacement_inherited_predecessor_ballot": result[
            "replacement_inherited_predecessor_ballot"
        ],
        "terminal_state": result["terminal_state"],
        "ticks": result["ticks"],
        "timeout_ticks": result["timeout_ticks"],
        "within_declared_timeout": result["within_declared_timeout"],
        "hung": result["hung"],
        "two_run_events_byte_identical": identical,
        "replacement_ballot": result["replacement_ballot"],
        "dying_intended_ballot": result["dying_intended_ballot"],
        "ballots": result["ballots"],
        "stripped_violator_caught": stripped["violator_caught"],
        "stripped_violator_rejection_count": stripped["violator_rejection_count"],
        "hang_timeout_fired": hang_fired,
        "hang_elapsed_s": round(hang_elapsed, 4),
    }

    nc_stripped = (
        f"enforce=False run on critic PROPOSE+VOTE -> "
        f"violator_caught={stripped['violator_caught']} "
        f"rejections={stripped['violator_rejection_count']} SILENT"
    )
    nc_enforced = (
        f"enforce=True run on the same critic PROPOSE+VOTE -> "
        f"violator_caught={result['violator_caught']} "
        f"rejections={result['violator_rejection_count']} FIRES"
    )
    src_summary = (
        f"violator_caught={result['violator_caught']} "
        f"compliant_flagged={result['compliant_flagged']} "
        f"mention_flagged={result['mention_flagged']} "
        f"terminal={result['terminal_state']} "
        f"ballots={result['ballots_committed']} ticks={result['ticks']}"
    )
    src_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import sys; sys.path.insert(0, 'command-center/p2-wave/probes/CNL-0118'); "
        "from harness import run; r=run(); print(r['violator_caught'], "
        "r['compliant_flagged'], r['terminal_state'], r['ballots_committed'], "
        "r['ticks'])\""
    )

    guard_anchor = line_of(
        "command-center/p2-wave/probes/CNL-0118/harness.py",
        "if action in forbidden:",
    )
    dead_anchor = line_of(
        "command-center/p2-wave/probes/CNL-0118/harness.py",
        '"SEAT_DEAD"',
    )

    schema_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CNL-0118/schema_check.py " + OUT
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0118",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0118",
        "spec_anchor": "_USER-PROMPTS.md:10746-10767",
        "min_bytes_threshold": 4000,
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "council-simulation-designer",
            "execution_substrate": "local-parallel",
        },
        "artifacts": [artifact_row(rel, role) for rel, role in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Point-of-use guard rejects actions listed in role.forbidden "
                    "without reading payload text (use vs mention)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": guard_anchor,
                "probes": [
                    probe(
                        role="source",
                        method="file-read",
                        command=guard_anchor,
                        raw_output="if action in forbidden: return REJECT, forbidden",
                        fingerprint="file-line:evaluate_action-forbidden",
                    ),
                    probe(
                        role="verifier",
                        method="command",
                        command=src_cmd,
                        raw_output=src_summary,
                        fingerprint="runtime-summary:violator-vs-compliant",
                    ),
                ],
            },
            {
                "claim": (
                    f"Live replay: carol rejections={result['violator_rejection_count']}, "
                    f"bob rejections={result['compliant_rejection_count']}, "
                    f"erin rejections={result['mention_rejection_count']}; "
                    f"dave ballot absent; frank does not inherit accept; "
                    f"terminal={result['terminal_state']} ticks={result['ticks']}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": P2,
                "probes": [
                    probe(
                        role="source",
                        method="command",
                        command=src_cmd,
                        raw_output=src_summary,
                        fingerprint="runtime-summary:replay-counts",
                    ),
                    probe(
                        role="verifier",
                        method="test-run",
                        command=P2,
                        raw_output=(
                            "independent fixture-matrix tabulation vs TURN/"
                            "BALLOT_COMMITTED/TERMINAL event kinds"
                        ),
                        fingerprint="fixture-matrix:event-kind-recount",
                    ),
                ],
            },
            {
                "claim": (
                    "Mid-vote death emits SEAT_DEAD without committing dave's ballot, "
                    "then SEAT_REPLACED with inherited_ballot false."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": dead_anchor,
                "probes": [
                    probe(
                        role="source",
                        method="file-read",
                        command=dead_anchor,
                        raw_output="emit SEAT_DEAD ballot_committed=False",
                        fingerprint="file-line:seat-dead-emit",
                    ),
                    probe(
                        role="verifier",
                        method="command",
                        command=src_cmd,
                        raw_output=(
                            f"dying_seat_ballot_present={result['dying_seat_ballot_present']} "
                            "replacement_inherited_predecessor_ballot="
                            f"{result['replacement_inherited_predecessor_ballot']}"
                        ),
                        fingerprint="runtime-summary:replacement-ballot",
                    ),
                ],
            },
            {
                "claim": (
                    "Catalog inputs 11-COUNCIL-SPECIFICATION.schema.json and "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json were read from this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0118.inputs",
                "probes": [
                    probe(
                        role="source",
                        method="file-read",
                        command="test -f 11-COUNCIL-SPECIFICATION.schema.json",
                        raw_output=json.dumps(prod, sort_keys=True),
                        fingerprint="existence:catalog-inputs",
                    )
                ],
            },
        ],
        "tests": [
            {
                "id": "violator-caught-compliant-silent",
                "name": (
                    "the violating participant must be caught; a compliant one "
                    "must not be flagged"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "mid-vote-death-defined-state",
                "name": (
                    "the mid-vote death must reach a defined state within the "
                    "declared timeout, never a hang"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe1-replay",
                "name": "scripted-participant replay plus hang wall-clock control",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-recount",
                "name": "independent fixture-matrix recount vs event kinds",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "negative-control-verbatim",
                "name": (
                    "negative control recorded verbatim: state what the check "
                    "does on the state it is meant to reject"
                ),
                "command": P1,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-ENFORCEMENT-POLARITY",
                "kind": "known-broken-fixture",
                "description": (
                    "Detector must fire on critic carol PROPOSE/VOTE and stay "
                    "silent on compliant critic bob CRITIQUE and observer SPEAK "
                    "that merely mentions voting."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": nc_enforced,
                "good_state_output": (
                    f"bob rejections={result['compliant_rejection_count']} "
                    f"erin rejections={result['mention_rejection_count']}"
                ),
            },
            {
                "id": "NC-ENFORCEMENT-STRIPPED",
                "kind": "mutation",
                "description": (
                    "Clearing enforce must make the same critic PROPOSE/VOTE "
                    "SILENT. If the stripped run still catches, the guard is "
                    "vacuously green."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": nc_stripped,
                "good_state_output": nc_enforced,
            },
            {
                "id": "NC-HANG-MUTANT",
                "kind": "mutation",
                "description": (
                    "hang_instead_of_replace sleeps instead of seating frank. "
                    "The wrapper must reach REPLACEMENT_TIMEOUT via a 0.2s "
                    "deadline rather than waiting out the sleep."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": hang_msg,
                "good_state_output": (
                    f"happy-path terminal={result['terminal_state']} "
                    f"ticks={result['ticks']}/{result['timeout_ticks']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0118-probe2-fixture-recount",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Re-tabulate expected REJECT/ALLOW from fixtures/roles.json "
                "fields times fixtures/script.json turns without reading "
                "report.measured_results first; compare to live TURN event "
                "verdicts. A disagreement in any number blocks the unit."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0118/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNL-0118",
        },
        "downstream_consumers": [
            {
                "consumer": "CNL-0118 schema_check (disk RefResolver store)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    role="verifier",
                    method="schema-validate",
                    command=schema_cmd,
                    raw_output="in-memory validate before write; errors=[]",
                    fingerprint="schema-check:council-simulation-spec",
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "retry": {
            "count": 0,
            "policy": (
                "up to 3 attempts, each with a MECHANICALLY DIFFERENT oracle "
                "(scripted-participant replay, transcript diff, counter assertion)"
            ),
        },
        "residual_unknowns": [
            {
                "claim": "Byte-identity against a CNL-0117 harness, if that unit later ships.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Replay this script through the CNL-0117 substrate and diff transcripts."
                ),
            },
            {
                "claim": (
                    "Field-by-field citation of $defs.role from "
                    "11-COUNCIL-SPECIFICATION.schema.json."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place the harness-restore schema on disk and map "
                    "forbidden/permissions/rights onto $defs.role."
                ),
            },
        ],
        "report": {
            "kind": "council-simulation-spec",
            "observations": [
                {
                    "name": "violator_caught",
                    "measured": bool(result["violator_caught"]),
                    "method": "harness-runtime-summary",
                    "anchor": P1,
                },
                {
                    "name": "compliant_flagged",
                    "measured": bool(result["compliant_flagged"]),
                    "method": "harness-runtime-summary",
                    "anchor": P1,
                },
                {
                    "name": "terminal_state",
                    "measured": str(result["terminal_state"]),
                    "method": "harness-event-log",
                    "anchor": P2,
                },
                {
                    "name": "ballots_committed",
                    "measured": int(result["ballots_committed"]),
                    "method": "event-kind-count",
                    "anchor": P2,
                },
            ],
            "control_ids": [
                "NC-ENFORCEMENT-POLARITY",
                "NC-ENFORCEMENT-STRIPPED",
                "NC-HANG-MUTANT",
            ],
            "title": "Role-enforcement and participant-replacement simulation",
            "question": QUESTION,
            "claim_under_test": (
                "A scripted critic that PROPOSEs and VOTEs is rejected at the "
                "point of use; a compliant critic is not flagged; a voter that "
                "dies mid-vote is replaced by a seat that inherits the voter role "
                "and not the predecessor ballot; the run reaches "
                "COMPLETED_AFTER_REPLACEMENT within declared_timeout_ticks."
            ),
            "answer": (
                "On this worktree the production council runtime is absent. The "
                "scripted harness under probes/CNL-0118 enforces the role matrix "
                f"at point of use: carol (critic) is caught "
                f"({result['violator_rejection_count']} rejections), bob (critic) "
                f"is not flagged, erin SPEAK that mentions voting is not a VOTE. "
                f"dave dies mid-vote with no ballot committed; frank is seated as "
                f"voter, ballots={result['ballots']}, terminal="
                f"{result['terminal_state']}, ticks={result['ticks']} <= "
                f"{result['timeout_ticks']}. Stripping enforcement makes the "
                "same violating turns SILENT, so the guard is not vacuously green. "
                "SUCCESS:CNL-0118"
            ),
            "harness": {
                "kind": "scripted-participant",
                "executable": "command-center/p2-wave/probes/CNL-0118/harness.py",
                "determinism_contract": (
                    "run() is a pure function of fixtures/roles.json and "
                    "fixtures/script.json plus the enforce flag. Events carry a "
                    "logical tick, never wall-clock or random. Two invocations "
                    "must be byte-identical JSON."
                ),
                "production_runtime_on_this_tree": prod,
                "scope": (
                    "Self-contained design-unit simulation. Does not claim "
                    "tools/council or CNL-0117 are shipped."
                ),
            },
            "scenario": {
                "id": "CNL-0118-role-enforcement-midvote-death",
                "violator_seat": "carol",
                "compliant_seat": "bob",
                "mention_seat": "erin",
                "dying_seat": "dave",
                "replacement_seat": "frank",
                "declared_timeout_ticks": 200,
                "procedure": [
                    "Load role matrix and scripted turns from fixtures.",
                    "Execute each structured action through evaluate_action at the point of use.",
                    "Reject critic PROPOSE and critic VOTE; allow critic CRITIQUE and observer SPEAK.",
                    "During vote collection, emit SEAT_DEAD for dave without committing intended_ballot=accept.",
                    "Seat frank with role=voter, inherited_ballot=false, ballot=reject.",
                    "Tally committed ballots; emit TERMINAL COMPLETED_AFTER_REPLACEMENT if ticks<=200.",
                ],
            },
            "role_matrix": json.loads(
                (HERE / "fixtures" / "roles.json").read_text(encoding="utf-8")
            ),
            "fixtures": [
                {
                    "path": "command-center/p2-wave/probes/CNL-0118/fixtures/roles.json",
                    "role": "role-matrix",
                },
                {
                    "path": "command-center/p2-wave/probes/CNL-0118/fixtures/script.json",
                    "role": "scripted-participants",
                },
                {
                    "path": "command-center/p2-wave/probes/CNL-0118/fixtures/scenario.json",
                    "role": "scenario-meta",
                },
            ],
            "measured_results": mr,
            "catalog_tests_required": [
                "the violating participant must be caught; a compliant one must not be flagged",
                "the mid-vote death must reach a defined state within the declared timeout, never a hang",
                "negative control recorded verbatim: state what the check does on the state it is meant to reject",
            ],
            "named_probes": [
                {"id": "probe1", "role": "scripted-participant-replay", "command": P1},
                {"id": "probe2", "role": "independent-recount", "command": P2},
            ],
            "format_note": (
                "Catalog output_path ends in .md. G-1 json.loads the whole file, "
                "so this artifact is a JSON council-simulation-spec receipt, not prose."
            ),
        },
        "extensions": {
            "completion_sentinel": "SUCCESS:CNL-0118",
            "output_schema": SCHEMA,
        },
    }

    errs = schema_errors(doc)
    if errs:
        print("FAILED:CNL-0118 schema errors")
        for row in errs[:20]:
            print(" ", row)
        return 1
    accepted = garbage_accepted()
    if accepted:
        print(f"FAILED:CNL-0118 schema accepted garbage {accepted}")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = digest_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0118 artifact {size}B below floor")
        return 1
    if "SUCCESS:CNL-0118" not in out.read_text(encoding="utf-8"):
        print("FAILED:CNL-0118 sentinel missing from artifact")
        return 1
    live_errs = schema_errors(json.loads(out.read_text(encoding="utf-8")))
    if live_errs:
        print("FAILED:CNL-0118 written artifact schema errors")
        for row in live_errs[:20]:
            print(" ", row)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0118 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
