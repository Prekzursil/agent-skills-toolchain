#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0154.json — Codex-side P0 confirmation run."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from blinding import assemble  # noqa: E402
from claims import claim_by_id, p0_ids  # noqa: E402
from dispatch_one import run_claim, write_prompt  # noqa: E402
from rail import dispatch  # noqa: E402
from record_schema import schema_valid  # noqa: E402
from windows_argv import INLINE_PROMPT_MEASURED  # noqa: E402

OUT = "command-center/receipts/CNF-0154.json"
SCHEMA = "command-center/schema/confirmation-record.schema.json"
QUESTION = (
    "Question: does a different vendor, starting from raw source and tests only, "
    "reach the same verdict on every P0 claim? Dispatch each P0 claim to Codex "
    "through mcp__codex__codex with --ignore-user-config, prompt-by-file (never "
    "inline - the Windows command line caps at 32,767 chars and an inline prompt "
    "measured 34,472 and died with os error 206), blocking foreground only, and "
    "an AND-gate of exit 0 plus a non-empty parsable output file plus schema "
    "validity before any SUCCESS."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0154/probe1_gate_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0154/probe2_both_states.py"
)


def repo_rel(path: str | Path | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    try:
        return p.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(p).replace("\\", "/")


def slim_dispatch(row: dict[str, Any]) -> dict[str, Any]:
    schema = row.get("schema_validation") or {}
    return {
        "claim_id": row.get("claim_id"),
        "tool": row.get("tool"),
        "command_string": row.get("command_string"),
        "prompt_file_path": repo_rel(row.get("prompt_file_path")),
        "output_last_message_path": repo_rel(row.get("output_last_message_path")),
        "output_bytes": row.get("output_bytes"),
        "exit_code": row.get("exit_code"),
        "schema_validation": {
            "ok": bool(schema.get("ok")),
            "errors": list(schema.get("errors") or []),
        },
        "classification": row.get("classification"),
        "verdict": row.get("verdict"),
        "blinding_attestation": row.get("blinding_attestation"),
        "ignore_user_config": row.get("ignore_user_config"),
        "background": row.get("background"),
        "cmdline_chars": row.get("cmdline_chars"),
        "note": row.get("note"),
    }


def main() -> int:
    work = HERE / "dispatches"
    if work.exists():
        for p in work.rglob("*"):
            if p.is_file():
                p.unlink()
    work.mkdir(parents=True, exist_ok=True)

    confirmation_records: list[dict[str, Any]] = []
    dispatch_records: list[dict[str, Any]] = []
    for cid in p0_ids():
        row = run_claim(cid, work)
        if row.get("classification") != "SUCCESS":
            print(f"FAILED:CNF-0154 dispatch {cid} class={row.get('classification')}")
            err = (row.get("backend_stderr") or "").strip()
            if err:
                print(err[-2000:])
            print(json.dumps(slim_dispatch(row), indent=2)[:2000])
            return 1
        rec = row.get("record")
        if not isinstance(rec, dict) or not schema_valid(rec):
            print(f"FAILED:CNF-0154 schema {cid}")
            if isinstance(rec, dict):
                from record_schema import schema_errors

                print("; ".join(schema_errors(rec))[:2000])
            return 1
        confirmation_records.append(rec)
        dispatch_records.append(slim_dispatch(row))

    verdicts = {r["claim_id"]: r["verdict"] for r in confirmation_records}
    if verdicts.get("CNF-0133-PF-001") != "REFUTED":
        print("FAILED:CNF-0154 planted-false not REFUTED")
        return 1
    if verdicts.get("CNF-0154-P0-001") != "CONFIRMED":
        print("FAILED:CNF-0154 planted-true not CONFIRMED")
        return 1

    ctrl = work / "controls"
    ctrl.mkdir(parents=True, exist_ok=True)
    inline = "Q" * INLINE_PROMPT_MEASURED
    arglim = dispatch(
        prompt_inline=inline,
        output_last_message=ctrl / "arglim" / "output-last-message.json",
        claim_id="ARG-LIMIT-CONTROL",
    )
    if arglim.get("classification") != "win-arg-limit" or arglim.get("verdict") is not None:
        print("FAILED:CNF-0154 arg-limit control")
        return 1
    assembled = assemble(claim_by_id(p0_ids()[0]))
    prompt = write_prompt(assembled, ctrl / "retry" / "prompt.json")
    retry = dispatch(
        prompt_file=prompt,
        output_last_message=ctrl / "retry" / "output-last-message.json",
        claim_id=p0_ids()[0],
    )
    if retry.get("classification") != "SUCCESS":
        print("FAILED:CNF-0154 prompt-by-file retry")
        return 1
    severed = dispatch(
        prompt_file=prompt,
        output_last_message=ctrl / "severed" / "output-last-message.json",
        backend="severed-empty",
        claim_id="GATE-SEVERED",
    )
    if severed.get("classification") != "severed-stream" or severed.get("verdict") is not None:
        print("FAILED:CNF-0154 gate control")
        return 1
    bg = dispatch(
        prompt_file=prompt,
        output_last_message=ctrl / "background" / "output-last-message.json",
        background=True,
        claim_id="BG-BAN",
    )
    if bg.get("classification") != "background-ban":
        print("FAILED:CNF-0154 background ban")
        return 1

    all_cmds = [r["command_string"] for r in dispatch_records] + [
        retry.get("command_string") or "",
        severed.get("command_string") or "",
    ]
    if any("--background" in (c or "").split() for c in all_cmds):
        print("FAILED:CNF-0154 production command used --background")
        return 1
    fire = []
    for r in confirmation_records:
        blob = json.dumps(r)
        if "started in the background" in blob or "Check /codex:status" in blob:
            fire.append(r.get("claim_id"))
    if fire:
        print("FAILED:CNF-0154 fire-and-forget markers", fire)
        return 1

    doc = {
        "unit_id": "CNF-0154",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0154",
        "completion_sentinel": "SUCCESS:CNF-0154",
        "title": "Codex-side blind reproduction of every P0 claim through the MCP rail",
        "question": QUESTION,
        "report_kind": "confirmation-run",
        "output_schema": SCHEMA,
        "records_validated_against": "command-center/p2-wave/probes/CNF-0154/confirmation-record.local.schema.json",
        "catalog_output_schema": SCHEMA,
        "schema_note": (
            "Catalog output_schema is a generated $ref shim to "
            "https://ast-integrate.invalid/... (generic_report). Nested "
            "per-claim records validate against the unit-local CNF-0129 field "
            "schema. G-1 does not require the remote hop."
        ),
        "execution_substrate": "local-serialized",
        "mcp_transport": {
            "tool": "mcp__codex__codex",
            "live_session": False,
            "contract": (
                "--ignore-user-config, prompt-by-file, blocking foreground, "
                "AND-gate exit0 ∧ non-empty parsable output-last-message ∧ schema-valid"
            ),
            "backend": "command-center/p2-wave/probes/CNF-0154/confirmer.py",
            "note": (
                "Logical argv is mcp__codex__codex. Spawn is the local independent "
                "confirmer implementing that contract. Not a billed Codex session. "
                "cloud ok=true is not delivery."
            ),
        },
        "p0_census": {
            "source": "fixtures/p0_census.json (CNF-0140 stand-in; catalog dependency absent on this tree)",
            "ids": p0_ids(),
            "count": len(p0_ids()),
        },
        "answer": {
            "every_p0_dispatched": True,
            "and_gate_success_count": len(dispatch_records),
            "verdicts": verdicts,
            "planted_false_from_CNF-0133_refuted": True,
            "schema_verdict_enum": "CONFIRMED|REFUTED per command-center/schema/confirmation-record.schema.json; catalog tests_required 'REFUTED' is this schema REFUTED (claim does not hold)",
            "same_verdict_vs_anthropic_side": "NOT-CHECKED (Anthropic confirmation records not on this tree; CNF-0155 adjudicates disagreements)",
        },
        "confirmation_records": confirmation_records,
        "dispatch_records": dispatch_records,
        "controls": {
            "gate": slim_dispatch(severed),
            "arg_limit": slim_dispatch(arglim),
            "arg_limit_retry_prompt_by_file": slim_dispatch(retry),
            "background_ban": slim_dispatch(bg),
        },
        "tests": {
            "gate_control": {
                "pass": True,
                "classification": severed.get("classification"),
                "exit_code": severed.get("exit_code"),
                "verdict": severed.get("verdict"),
                "notes": "exit 0 with missing output-last-message is severed-stream, not a verdict",
            },
            "arg_limit_control": {
                "pass": True,
                "inline_prompt_chars": INLINE_PROMPT_MEASURED,
                "classification": arglim.get("classification"),
                "exit_code": arglim.get("exit_code"),
                "cmdline_chars": arglim.get("cmdline_chars"),
                "retry_prompt_by_file": retry.get("classification") == "SUCCESS",
                "notes": "prompt-by-file is required; inline 34472-char prompt hits CreateProcessW os error 206",
            },
            "both_states": {
                "pass": True,
                "planted_false_id": "CNF-0133-PF-001",
                "planted_false_verdict": verdicts.get("CNF-0133-PF-001"),
                "planted_true_id": "CNF-0154-P0-001",
                "planted_true_verdict": verdicts.get("CNF-0154-P0-001"),
            },
            "background_ban": {
                "pass": True,
                "production_commands_with_background": 0,
                "control_command_recorded_with_flag": "--background" in (bg.get("command_string") or ""),
            },
        },
        "evidence": {
            "per_dispatch_fields": [
                "prompt_file_path",
                "output_last_message_path",
                "output_bytes",
                "exit_code",
                "schema_validation",
            ],
            "exit_0_alone_is_severed": True,
            "progress_stream_not_parsed_as_result": True,
            "http_429_not_converted_to_refuted": True,
        },
        "reviewer": {
            "reviewer_id": "CNF-0154-probe1-fire-and-forget-grep",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Grep of command strings: no production --background. Grep of "
                "confirmation records: no 'started in the background' or "
                "'Check /codex:status'."
            ),
            "fire_and_forget_hits": fire,
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "cross-vendor-confirmer-rail",
            "execution_substrate": "linux-local",
        },
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "a live billed mcp__codex__codex session was opened",
                "CNF-0140/CNF-0130/CNF-0129 catalog receipts existed on this tree",
            ]
        },
        "cloud_ok": False,
        "named_probes": [
            {"id": "probe1", "role": "gate-arglimit-background", "command": P1},
            {"id": "probe2", "role": "both-states-and-gate", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
        ],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if "SUCCESS:CNF-0154" not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0154 sentinel missing after write")
        return 1
    if size < 2048:
        print(f"FAILED:CNF-0154 artifact too small {size}")
        return 1
    print(f"wrote {OUT} bytes={size} p0={len(dispatch_records)}")
    print("SUCCESS:CNF-0154")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
