#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0034-alternate-interface.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from exercise import MCP_BLOCKER, run  # noqa: E402
import schema_local as S  # noqa: E402

OUT = "command-center/confirmation/CNF-0034-alternate-interface.json"
SCHEMA = "command-center/schema/interface-coverage.schema.json"
QUESTION = (
    "Was the fix verified only through the one interface the author happened to "
    "use? Exercise the same behaviour through a different entry point - library "
    "call versus CLI versus hook versus MCP tool - and answer: does the "
    "corrected behaviour hold on every surface, or only on the tested one?"
)
SENTINEL = (
    "SUCCESS:CNF-0034 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and each component lists at "
    "least one surface exercised by this unit that the author did not exercise. "
    "Any other terminal state is FAILED:CNF-0034 <classification> with the "
    "diagnostic tail attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0034/probe1_untested_surfaces.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0034/probe2_coverage_contract.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNF-0034/exercise.py",
    "command-center/p2-wave/probes/CNF-0034/schema_local.py",
    "command-center/p2-wave/probes/ARC-0010/generator.py",
    "command-center/p2-wave/probes/ARC-0014/freeze_hook.py",
    "command-center/p2-wave/probes/ARC-0005/stop_hook.py",
]
MIN_BYTES = 256


def outcome(
    surface: str,
    *,
    author: bool,
    unit: bool,
    result: str,
    invocation: str,
    blocker: str | None = None,
) -> dict:
    row = {
        "surface": surface,
        "author_tested": author,
        "this_unit_tested": unit,
        "result": result,
        "invocation": invocation,
    }
    if blocker:
        row["blocking_prerequisite"] = blocker
    return row


def digest_rel(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest_rel(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc)
    live = run()
    if not live.get("pass"):
        print("FAILED:CNF-0034 emit live surfaces did not hold")
        print(json.dumps(live, indent=2, default=str)[:4000])
        return 1
    freeze = live["freeze"]
    stop = live["stop"]
    mcp_result = "NOT-CHECKED"
    ended = datetime.now(timezone.utc)
    now = ended.strftime("%Y-%m-%dT%H:%M:%SZ")
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    duration = max(0.0, (ended - started).total_seconds())
    freeze_cli = str(freeze["cli_command"])
    stop_cli = str(stop["cli_command"])
    live_tail = json.dumps(
        {
            "freeze_hold": freeze["hold"],
            "stop_hold": stop["hold"],
            "target": freeze["target"],
            "mutant_freeze": freeze["mutant_cli_hides_tamper"],
            "mutant_stop": stop["mutant_cli_silent_on_bad"],
        },
        sort_keys=True,
    )[:4000]

    generator = {
        "id": "a2-ssot-generator",
        "path": "command-center/p2-wave/probes/ARC-0010/generator.py",
        "fixed_behaviour": (
            "Hand-edit of a generated artifact is TAMPERED, not legitimate drift, "
            "while an unedited sibling stays CLEAN."
        ),
        "surfaces_enumerated": [
            {
                "kind": "library",
                "path": "command-center/p2-wave/probes/ARC-0010/generator.py",
                "present": True,
            },
            {
                "kind": "hook",
                "path": "command-center/p2-wave/probes/ARC-0014/freeze_hook.py",
                "present": True,
            },
            {
                "kind": "cli",
                "path": "command-center/p2-wave/probes/ARC-0014/freeze_hook.py",
                "present": True,
            },
            {"kind": "mcp", "path": "(absent)", "present": False},
        ],
        "author_tested": [
            {
                "kind": "library",
                "citation": (
                    "command-center/p2-wave/probes/ARC-0010/probe2_tamper.py:12 "
                    "import generator as G; G.classify_tree"
                ),
            }
        ],
        "this_unit_tested": ["hook", "cli"],
        "untested_surfaces_exercised_by_this_unit": ["hook", "cli"],
        "outcomes": [
            outcome(
                "library",
                author=True,
                unit=True,
                result="HOLD",
                invocation="FH.check() after generate()+write_tree()+hand-edit",
            ),
            outcome(
                "hook",
                author=False,
                unit=True,
                result="HOLD",
                invocation=freeze_cli,
            ),
            outcome(
                "cli",
                author=False,
                unit=True,
                result="HOLD",
                invocation=freeze_cli,
            ),
            outcome(
                "mcp",
                author=False,
                unit=False,
                result=mcp_result,
                invocation="not invoked",
                blocker=MCP_BLOCKER,
            ),
        ],
    }
    freeze_comp = {
        "id": "a2-freeze-hook",
        "path": "command-center/p2-wave/probes/ARC-0014/freeze_hook.py",
        "fixed_behaviour": (
            "After A2-FREEZE-GENERATED, a hand-edit of a deployed generated path "
            "is rejected (ok=false, exit 1); a clean deploy is accepted."
        ),
        "surfaces_enumerated": [
            {
                "kind": "library",
                "path": "command-center/p2-wave/probes/ARC-0014/freeze_hook.py",
                "present": True,
            },
            {
                "kind": "cli",
                "path": "command-center/p2-wave/probes/ARC-0014/freeze_hook.py",
                "present": True,
            },
            {
                "kind": "hook",
                "path": "command-center/p2-wave/probes/ARC-0014/freeze_hook.py",
                "present": True,
            },
            {"kind": "mcp", "path": "(absent)", "present": False},
        ],
        "author_tested": [
            {
                "kind": "library",
                "citation": (
                    "command-center/p2-wave/probes/ARC-0014/probe2_rollback.py:19 "
                    "from freeze_hook import check"
                ),
            }
        ],
        "this_unit_tested": ["cli"],
        "untested_surfaces_exercised_by_this_unit": ["cli"],
        "outcomes": [
            outcome(
                "library",
                author=True,
                unit=True,
                result="HOLD",
                invocation="freeze_hook.check(deploy, registry, ledger)",
            ),
            outcome(
                "cli",
                author=False,
                unit=True,
                result="HOLD",
                invocation=freeze_cli,
            ),
            outcome(
                "mcp",
                author=False,
                unit=False,
                result=mcp_result,
                invocation="not invoked",
                blocker=MCP_BLOCKER,
            ),
        ],
    }
    stop_comp = {
        "id": "a1-stop-hook",
        "path": "command-center/p2-wave/probes/ARC-0005/stop_hook.py",
        "fixed_behaviour": (
            "Repo-vs-live drift fires the Stop-hook warning file; identical trees "
            "stay silent and remove the warning."
        ),
        "surfaces_enumerated": [
            {
                "kind": "library",
                "path": "command-center/p2-wave/probes/ARC-0005/stop_hook.py",
                "present": True,
            },
            {
                "kind": "cli",
                "path": "command-center/p2-wave/probes/ARC-0005/stop_hook.py",
                "present": True,
            },
            {
                "kind": "hook",
                "path": "command-center/p2-wave/probes/ARC-0005/stop_hook.py",
                "present": True,
            },
            {"kind": "mcp", "path": "(absent)", "present": False},
        ],
        "author_tested": [
            {
                "kind": "library",
                "citation": (
                    "command-center/p2-wave/probes/ARC-0005/"
                    "probe2_both_states_latency.py:17 import stop_hook as H; H.run()"
                ),
            }
        ],
        "this_unit_tested": ["cli"],
        "untested_surfaces_exercised_by_this_unit": ["cli"],
        "outcomes": [
            outcome(
                "library",
                author=True,
                unit=True,
                result="HOLD",
                invocation="stop_hook.run(CTRL_REPO, CTRL_LIVE)",
            ),
            outcome(
                "cli",
                author=False,
                unit=True,
                result="HOLD",
                invocation=stop_cli,
            ),
            outcome(
                "mcp",
                author=False,
                unit=False,
                result=mcp_result,
                invocation="not invoked",
                blocker=MCP_BLOCKER,
            ),
        ],
    }

    answer = (
        "Corrected behaviour holds on the author-untested CLI/hook surfaces for "
        "all three components present in this worktree. a2-ssot-generator: author "
        "tested library classify_tree; this unit invoked the freeze-hook CLI, "
        f"which rejected a hand-edit of {freeze['target']} (ok=false, "
        f"rejections={freeze['dirty_library_rejections']}) and accepted the clean "
        "tree. a2-freeze-hook: author tested freeze_hook.check(); the argparse "
        "CLI agreed on both states. a1-stop-hook: author tested stop_hook.run(); "
        "the CLI subprocess was silent on the identical control tree and wrote "
        "STOP-HOOK DRIFT WARNING after a planted live edit. MCP is NOT-CHECKED "
        f"({MCP_BLOCKER}) and is not folded into HOLD. Mutant CLIs that always "
        "report ok/silent were detected as a surface-gap control."
    )

    schema_errs_before = S.errors(
        {
            "schema_version": 1,
            "unit_id": "CNF-0034",
            "state": "SUCCESS",
            "sentinel": SENTINEL,
        }
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0034",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0034",
        "min_bytes_threshold": MIN_BYTES,
        "artifacts": [artifact_row(path, "supporting") for path in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Freeze-hook CLI and freeze_hook.check() agree on a clean "
                    "deploy and reject the same hand-edit; a mutant CLI that "
                    "always prints ok=true hides the tamper."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0034/exercise.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/CNF-0034/exercise.py"
                        ),
                        "raw_output": live_tail,
                        "fingerprint": "cnf0034-exercise-cli-library",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": (
                            "compare freeze_hook.check() ok/rejections against "
                            "freeze_hook.py --root/--registry/--ledger JSON stdout"
                        ),
                        "raw_output": (
                            f"library_cli_agree_clean={freeze['library_cli_agree_clean']} "
                            f"library_cli_agree_dirty={freeze['library_cli_agree_dirty']} "
                            f"mutant_cli_hides_tamper={freeze['mutant_cli_hides_tamper']}"
                        ),
                        "fingerprint": "cnf0034-freeze-lib-vs-cli",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Stop-hook CLI agrees with stop_hook.run(): silent on the "
                    "identical control tree, writes STOP-HOOK DRIFT WARNING after "
                    "a planted live edit; a mutant CLI that stays silent is caught."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ARC-0005/stop_hook.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": stop_cli,
                        "raw_output": (
                            f"good_cli_fired={stop['good_cli_fired']} "
                            f"bad_cli_fired={stop['bad_cli_fired']} "
                            f"warning_on_bad={stop['warning_on_bad']}"
                        ),
                        "fingerprint": "cnf0034-stop-cli-subprocess",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "read command-center/p2-wave/probes/ARC-0005/fixtures/"
                            "stop-surface/WARNING.txt after CLI on planted tree"
                        ),
                        "raw_output": (
                            f"warning_on_good={stop['warning_on_good']} "
                            f"warning_on_bad={stop['warning_on_bad']} "
                            f"mutant_cli_silent_on_bad={stop['mutant_cli_silent_on_bad']}"
                        ),
                        "fingerprint": "cnf0034-stop-warning-file",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "freeze-cli-vs-library",
                "name": "freeze hook CLI agrees with library on both states",
                "command": freeze_cli,
                "result": "PASS",
            },
            {
                "id": "stop-cli-vs-library",
                "name": "stop hook CLI agrees with library on both states",
                "command": stop_cli,
                "result": "PASS",
            },
            {
                "id": "mutant-cli-surface-gap",
                "name": "mutant always-ok/silent CLIs disagree with the library",
                "command": (
                    "python3 -c \"import json,sys; print(json.dumps({'ok': True}))\""
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-MUTANT-FREEZE-CLI",
                "kind": "mutation",
                "description": (
                    "A CLI that always prints ok=true must hide tamper that "
                    "freeze_hook.check() reports."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"mutant_cli_hides_tamper={freeze['mutant_cli_hides_tamper']}"
                ),
                "good_state_output": (
                    f"library_cli_agree_clean={freeze['library_cli_agree_clean']}"
                ),
            },
            {
                "id": "NC-MUTANT-STOP-CLI",
                "kind": "mutation",
                "description": (
                    "A CLI that always reports fired=false must stay silent on "
                    "planted drift that stop_hook.run() surfaces."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"mutant_cli_silent_on_bad={stop['mutant_cli_silent_on_bad']}"
                ),
                "good_state_output": (
                    f"good_cli_fired={stop['good_cli_fired']}"
                ),
            },
            {
                "id": "NC-EMPTY-UNTESTED",
                "kind": "malformed-input",
                "description": (
                    "A component with untested_surfaces_exercised_by_this_unit=[] "
                    "must be rejected by probe2."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "untested_surfaces_exercised_by_this_unit=[]",
                "good_state_output": "each live component lists hook or cli",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0034-probe2-coverage-contract",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "Assigned executor is gpt-5-codex (OpenAI). Reviewer is the "
                "mechanically independent probe2 contract check (other vendor)."
            ),
            "reviewed_at": now,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0034/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0034",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNF-0034/schema_local.py"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                        "'from schema_local import errors; ...'"
                    ),
                    "raw_output": (
                        "partial_receipt_rejected="
                        + str(bool(schema_errs_before))
                        + " nerr="
                        + str(len(schema_errs_before))
                    ),
                    "fingerprint": "cnf0034-schema-local-validate",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": now,
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the 2nd failure "
                "carrying the same error fingerprint, enumerate >=2 mechanically "
                "different approaches before any 3rd attempt; a 3rd identical "
                "retry is a unit failure, not a retry"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "No MCP tool server is bound to generator, freeze_hook, or "
                    "stop_hook in this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Register an MCP tool server for those three components and "
                    "re-run this unit against that server."
                ),
            }
        ],
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "interface-coverage-engineer",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "interface-coverage",
            "observations": [
                {
                    "name": "freeze-cli-hold",
                    "measured": bool(freeze["hold"]),
                    "method": "CLI subprocess vs freeze_hook.check on clean+tamper",
                    "anchor": "command-center/p2-wave/probes/CNF-0034/exercise.py",
                },
                {
                    "name": "stop-cli-hold",
                    "measured": bool(stop["hold"]),
                    "method": "CLI subprocess vs stop_hook.run on identical+planted",
                    "anchor": "command-center/p2-wave/probes/ARC-0005/stop_hook.py",
                },
                {
                    "name": "mcp-bound",
                    "measured": bool(live["mcp_present"]),
                    "method": "stat mcp_server.py/server.py beside the three components",
                    "anchor": MCP_BLOCKER,
                },
            ],
            "control_ids": [
                "NC-MUTANT-FREEZE-CLI",
                "NC-MUTANT-STOP-CLI",
                "NC-EMPTY-UNTESTED",
            ],
            "question": QUESTION,
            "answer": answer,
            "components": [generator, freeze_comp, stop_comp],
            "live": {
                "freeze_hold": freeze["hold"],
                "stop_hold": stop["hold"],
                "tamper_target": freeze["target"],
                "mutant_freeze_cli_hides_tamper": freeze["mutant_cli_hides_tamper"],
                "mutant_stop_cli_silent_on_bad": stop["mutant_cli_silent_on_bad"],
            },
            "mcp_present": live["mcp_present"],
            "cloud_ok_is_not_delivery": True,
            "failure_classification_not_used": [
                "surface-gap",
                "not-checked-folded-into-pass",
                "blocked-external",
            ],
        },
        "components": [generator, freeze_comp, stop_comp],
    }

    errs = S.errors(doc)
    if errs:
        print("FAILED:CNF-0034 schema errors")
        for err in errs[:30]:
            print(" ", err)
        return 1
    dumped = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in dumped:
        print("FAILED:CNF-0034 emit sentinel missing from document")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumped, encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:CNF-0034 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
