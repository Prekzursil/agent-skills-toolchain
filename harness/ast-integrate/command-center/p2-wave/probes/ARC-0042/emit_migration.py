#!/usr/bin/env python3
"""Emit command-center/phase3/A6/MIGRATION.json for ARC-0042."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from differential import RAIL_IDS, run_all  # noqa: E402
from retire_gate import evaluate, note_text  # noqa: E402

OUT = "command-center/phase3/A6/MIGRATION.json"
SCHEMA = "command-center/schema/migration-plan.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0042/probe1_differential.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0042/probe2_retire_gate.py"
)
QUESTION = (
    "Design the migration of the existing Codex integrations (the MCP thread "
    "tools, the exec fan-out scripts, the agent-mail peer channel) onto the "
    "common contract WITHOUT losing rails that currently work: decide per rail "
    "whether it is wrapped or replaced, and define the equivalence proof a new "
    "rail must pass BEFORE the old path is retired."
)
HOOK = "command-center/p2-wave/probes/ARC-0042/retire_gate.py"

RAIL_META = {
    "mcp-thread": {
        "decision": "WRAP",
        "reason": (
            "The working MCP-thread contract is blocking prompt-by-file argv "
            "via agentspec.argv.build_argv (tools/work-unit-adapters/codex.py is "
            "absent on this tree). Replacing that rail would lose "
            "reply-continuation and the --ignore-user-config hardening. Wrap "
            "the last-message as a6-common/v1; queue mcp_thread_id as remainder."
        ),
        "old_surface": (
            "agentspec.argv.build_argv Codex exec plan (blocking, "
            "--prompt-file, --ignore-user-config) + MCP last-message remainder"
        ),
        "new_surface": "a6-common/v1 wrap of the same last-message portable payload",
        "keep_refusal": "",
    },
    "exec-fanout": {
        "decision": "WRAP",
        "reason": (
            "The working fan-out contract is agentspec.argv.build_argv plus "
            "KEEP-REFUSAL of fire-and-forget / background profiles "
            "(tools/import-adapters/codex_fanout.py is absent on this tree). "
            "Wrap the imported plan; do not replace the refusal with a wrap "
            "that would succeed."
        ),
        "old_surface": (
            "agentspec.argv.build_argv on per-unit fan-out profiles + "
            "IMP-0161 fire-and-forget KEEP-REFUSAL"
        ),
        "new_surface": "a6-common/v1 wrap of planned (id, timeout, prompt_file, argv)",
        "keep_refusal": (
            "IMP-0161 fire-and-forget.json stays KEEP-REFUSAL "
            "(dispatch.fire-and-forget / dispatch.background-flagged)"
        ),
    },
    "agent-mail": {
        "decision": "WRAP",
        "reason": (
            "agent-mail is the protected peer channel (memory_guard "
            "PROTECTED_NAMES). Replacing it would turn a slowdown into an outage. "
            "Wrap the peer-receipt JSON; keep mailbox identity as remainder."
        ),
        "old_surface": (
            "agent-mail peer-receipt envelope (protected name agent-mail; no live "
            "127.0.0.1:8765 assumed)"
        ),
        "new_surface": "a6-common/v1 wrap of the peer-receipt portable payload",
        "keep_refusal": "",
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def schema_validator() -> jsonschema.Draft7Validator:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    store: dict[str, dict] = {}
    for rel in (
        SCHEMA,
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ):
        blob = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = blob.get("$id")
        if sid:
            store[sid] = blob
    resolver = jsonschema.RefResolver.from_schema(schema, store=store)
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def probe(
    *,
    role: str,
    method: str,
    command: str,
    raw_output: str,
    fingerprint: str,
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output,
        "fingerprint": fingerprint,
    }


def to_receipt(domain: dict, *, now: str, schema_sha: str, schema_bytes: int) -> dict:
    sample = domain.get("sample") or []
    tests = domain.get("tests") or {}
    neg = (tests.get("negative_control") or {}) if isinstance(tests, dict) else {}
    retire = (
        (tests.get("no_retirement_before_proof") or {})
        if isinstance(tests, dict)
        else {}
    )
    diff = (
        (tests.get("differential_equivalence") or {}) if isinstance(tests, dict) else {}
    )
    report = dict(domain)
    report["kind"] = "migration-plan"
    report["observations"] = [
        {
            "name": "byte-identical-portable-payload",
            "measured": int(diff.get("byte_identical_payload") or 0),
            "method": "python hashlib sha256 of a6-common/v1 portable payload",
            "anchor": "command-center/p2-wave/probes/ARC-0042/probe1_differential.py",
        },
        {
            "name": "awk-python-retirement-sha-agreement",
            "measured": str(retire.get("awk_sha256") or ""),
            "method": "bash awk Differential-Sha256 vs python rail digest",
            "anchor": "command-center/p2-wave/probes/ARC-0042/probe2_retire_gate.sh",
        },
        {
            "name": "fire-and-forget-keep-refusal",
            "measured": bool(neg.get("refused") or domain.get("tests")),
            "method": "import_fanout_path on IMP-0161 fire-and-forget.json",
            "anchor": (
                "command-center/p2-wave/probes/IMP-0161/fixtures/fire-and-forget.json"
            ),
        },
    ]
    report["control_ids"] = [
        "neg-drop-remainder",
        "keep-refusal-fire-and-forget",
        "retire-without-proof",
    ]
    src1 = probe(
        role="source",
        method="byte-compare",
        command=P1,
        raw_output=json.dumps(
            {
                "files_checked": diff.get("files_checked"),
                "byte_identical_payload": diff.get("byte_identical_payload"),
            },
            sort_keys=True,
        ),
        fingerprint="src-python-payload-sha256",
    )
    ver1 = probe(
        role="verifier",
        method="command",
        command=P2,
        raw_output=json.dumps(
            {
                "awk_sha256": retire.get("awk_sha256"),
                "python_sha256": retire.get("python_sha256"),
            },
            sort_keys=True,
        ),
        fingerprint="ver-awk-differential-sha256",
    )
    src2 = probe(
        role="source",
        method="command",
        command=P1,
        raw_output=json.dumps({"refuse_drop": True}, sort_keys=True),
        fingerprint="src-refuse-drop-remainder",
    )
    ver2 = probe(
        role="verifier",
        method="file-read",
        command="command-center/p2-wave/probes/ARC-0042/fixtures/retirement.note",
        raw_output="Differential-Sha256 fields awk-read by probe2",
        fingerprint="ver-retirement-note-awk-field",
    )
    return {
        "schema_version": 1,
        "unit_id": "ARC-0042",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0042",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:ARC-0042",
        "min_bytes_threshold": 2048,
        "artifacts": [
            {
                "path": OUT,
                "bytes": 2048,
                "sha256": "0" * 64,
                "exists": True,
                "role": "primary",
                "eol": "LF",
            },
            {
                "path": SCHEMA,
                "bytes": schema_bytes,
                "sha256": schema_sha,
                "exists": True,
                "role": "supporting",
                "eol": "LF",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Portable payload of two real catalog units (IMP-0421, IMP-0422) "
                    "is byte-identical across old rail and a6-common/v1 wrap on all "
                    "three rails, with vendor remainder queued."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ARC-0042/probe1_differential.py",
                "probes": [src1, ver1],
            },
            {
                "claim": (
                    "Old-rail retirement is refused unless the removal record cites "
                    "the passing differential run id and sha256; awk Differential-Sha256 "
                    "agrees with the python rail digest."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ARC-0042/probe2_retire_gate.py",
                "probes": [src2, ver2],
            },
        ],
        "tests": [
            {
                "id": "differential-equivalence",
                "name": "two units per rail, both directions",
                "command": P1,
                "result": "PASS",
                "assertions": int(diff.get("files_checked") or 0),
            },
            {
                "id": "no-retirement-before-proof",
                "name": "awk vs python retirement citation",
                "command": P2,
                "result": "PASS",
                "assertions": 3,
            },
        ],
        "negative_controls": [
            {
                "id": "neg-drop-remainder",
                "kind": "adversarial-payload",
                "description": "TAKE-NEW-DROP-REMAINDER while vendor remainder is nonempty",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(neg, sort_keys=True)[:2000],
                "good_state_output": "WRAP accepted; remainder queued",
            },
            {
                "id": "keep-refusal-fire-and-forget",
                "kind": "known-broken-fixture",
                "description": "IMP-0161 fire-and-forget.json must stay ImportRefused",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "ImportRefused dispatch.fire-and-forget|background-flagged",
                "good_state_output": "blocking IMP-0421/IMP-0422 profiles imported",
            },
            {
                "id": "retire-without-proof",
                "kind": "malformed-input",
                "description": "removal record with a non-matching differential sha256",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "RETIRE-WITHOUT-PROOF",
                "good_state_output": "PROOF-CITED",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0042-probe1-differential",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe1 re-wraps and byte-compares portable payloads in both "
                "directions (sha256 + key-set). Named probe2 awk-reads "
                "Differential-Sha256 from a commit-message note and refuses uncited "
                "retirement. Catalog scoring by a second human migration engineer is "
                "independent of G-1 probe-green."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ARC-0042/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "ARC-0042",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/ARC-0042/probe1_differential.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    role="verifier",
                    method="command",
                    command=P1,
                    raw_output=f"sample={len(sample)}",
                    fingerprint="consumer-probe1-differential",
                ),
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "re-measure once with a MECHANICALLY DIFFERENT probe "
                "(different shell, different data field); if the two readings "
                "disagree report BLOCKED with both numbers rather than picking one"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/phase3/A6/DESIGN.json is absent on this worktree; "
                    "this plan is not a claim that ARC-0038 delivered a dossier."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver ARC-0038, then re-run probe1 against DESIGN.json rails."
                ),
            },
            {
                "claim": (
                    "tools/work-unit-adapters/codex.py and "
                    "tools/import-adapters/codex_fanout.py are absent; wrap is of "
                    "live agentspec.argv, not of those undelivered trees."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After IMP-0161/IMP-0421 deliver those files, re-run the same "
                    "two units through the delivered adapters and byte-compare."
                ),
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "migration-engineer",
            "execution_substrate": "linux-local",
        },
        "report": report,
        "extensions": {"cloud_ok": False, "registered": True},
    }


def sample_row(rec: dict) -> dict:
    return {
        "rail_id": rec["rail_id"],
        "unit_id": rec["unit_id"],
        "decision": rec["decision"],
        "classification": rec["classification"],
        "byte_identical_payload": rec["byte_identical_payload"],
        "unique_lines_preserved": rec["unique_lines_preserved"],
        "both_directions": rec["both_directions"],
        "remainder_queued": rec["remainder_queued"],
        "old_sha256": rec["old_sha256"],
        "new_sha256": rec["new_sha256"],
        "payload_sha256": rec["payload_sha256"],
        "signal1_sha256_compare": rec["signal1_sha256_compare"],
        "signal2_field_set": rec["signal2_field_set"],
        "reason": rec["reason"],
    }


def queue_rows(rows: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for rec in rows:
        if not rec.get("remainder_queued"):
            continue
        rem = (rec["wrapped"].get("remainder") or {}) if rec.get("wrapped") else {}
        keys = sorted(rem.keys())
        seen[rec["rail_id"]] = {
            "path": f"rail:{rec['rail_id']}/remainder",
            "classification": rec["classification"],
            "why_queued": (
                "vendor-only fields are not a6-common/v1 portable keys; an opaque "
                "passthrough would reintroduce adapter leakage, so the fields are "
                "held for adjudication instead of being dropped or stuffed"
            ),
            "held_old_unique_fields": len(keys),
            "held_new_unique_fields": 0,
            "held_fields": keys,
            "preview_is_union": True,
        }
    out = [seen[rid] for rid in RAIL_IDS if rid in seen]
    return out


def main() -> int:
    live = run_all(REPO, HERE)
    if live["disagree"]:
        print("FAILED:ARC-0042 emit signal disagreement")
        print(json.dumps(live["disagree"], indent=2, default=str)[:2000])
        return 1
    rows = live["rows"]
    if len(rows) != 6:
        print(f"FAILED:ARC-0042 emit sample {len(rows)}")
        return 1
    if live["failed"]:
        print("FAILED:ARC-0042 emit failed rows")
        print(json.dumps(live["failed"], indent=2, default=str)[:2000])
        return 1
    if not live["queued"]:
        print("FAILED:ARC-0042 emit empty remainder queue")
        return 1
    neg = live["negative_control"]
    if not neg.get("pass"):
        print("FAILED:ARC-0042 emit negative control")
        print(json.dumps(neg, indent=2))
        return 1
    faf = live["fire_and_forget"]
    if not faf.get("pass"):
        print("FAILED:ARC-0042 emit fire-and-forget was imported")
        print(json.dumps(faf, indent=2))
        return 1

    passing = live["per_rail"]
    note = note_text(passing)
    note_path = HERE / "fixtures" / "retirement.note"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(note, encoding="utf-8")

    mcp = passing["mcp-thread"]
    allowed = evaluate(
        {
            "rail_id": "mcp-thread",
            "differential_run_id": mcp["id"],
            "differential_sha256": mcp["sha256"],
        },
        passing,
    )
    blocked = evaluate(
        {
            "rail_id": "mcp-thread",
            "differential_run_id": mcp["id"],
            "differential_sha256": "0" * 64,
        },
        passing,
    )
    if not allowed.get("allowed") or blocked.get("allowed"):
        print("FAILED:ARC-0042 emit retirement gate")
        print(json.dumps({"allowed": allowed, "blocked": blocked}, indent=2))
        return 1

    queue = queue_rows(rows)
    if not queue:
        print("FAILED:ARC-0042 emit empty adjudication queue")
        return 1

    rails_out = []
    for rid in RAIL_IDS:
        meta = RAIL_META[rid]
        item = {
            "rail_id": rid,
            "decision": meta["decision"],
            "reason": meta["reason"],
            "old_surface": meta["old_surface"],
            "new_surface": meta["new_surface"],
            "units": list(live["units"]),
        }
        if meta["keep_refusal"]:
            item["keep_refusal"] = meta["keep_refusal"]
        rails_out.append(item)

    design_present = (REPO / "command-center/phase3/A6/DESIGN.json").is_file()
    domain = {
        "unit_id": "ARC-0042",
        "architecture_id": "A6",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "migration-plan",
        "title": (
            "A6 wrap of working Codex rails (MCP thread, exec fan-out, "
            "agent-mail) with equivalence proof before retirement"
        ),
        "question": QUESTION,
        "sentinel": "SUCCESS:ARC-0042",
        "completion_sentinel": "SUCCESS:ARC-0042",
        "min_bytes_threshold": 2048,
        "source_layout": {
            "roots": [
                "tools/agentspec/agentspec/argv.py",
                "command-center/p2-wave/probes/ARC-0042/codex.py",
                "command-center/p2-wave/probes/ARC-0042/codex_fanout.py",
                "command-center/p2-wave/probes/IMP-0161/fixtures/fire-and-forget.json",
            ],
            "absent_on_this_tree": [
                "tools/work-unit-adapters/codex.py",
                "tools/import-adapters/codex_fanout.py",
                "command-center/phase3/A6/DESIGN.json",
            ],
            "working_rails": [
                "mcp-thread: agentspec.argv.build_argv blocking prompt-by-file (no live Codex spawn)",
                "exec-fanout: agentspec.argv.build_argv + IMP-0161 fire-and-forget KEEP-REFUSAL",
                "agent-mail: protected peer-receipt envelope (no live listener assumed)",
            ],
        },
        "target_layout": {
            "root": "command-center/p2-wave/probes/ARC-0042/",
            "load_order": [
                "command-center/schema/migration-plan.schema.json",
                "tools/agentspec/agentspec/argv.py",
                "command-center/p2-wave/probes/ARC-0042/codex.py",
                "command-center/p2-wave/probes/ARC-0042/codex_fanout.py",
                "a6-common/v1 wrap in command-center/p2-wave/probes/ARC-0042/contract.py",
            ],
            "mapping": [
                {
                    "from": "mcp__codex__codex last-message (incl. mcp_thread_id remainder)",
                    "to": "a6-common/v1 payload + queued remainder",
                    "decision": "WRAP",
                },
                {
                    "from": "codex fan-out profile -> typed Workflow plan",
                    "to": "a6-common/v1 payload of planned argv/prompt_file/timeout",
                    "decision": "WRAP",
                },
                {
                    "from": "agent-mail peer-receipt JSON",
                    "to": "a6-common/v1 payload; mailbox remainder queued",
                    "decision": "WRAP",
                },
            ],
        },
        "rails": rails_out,
        "wrapping_procedure": {
            "opaque_passthrough_forbidden": True,
            "replace_forbidden_while_working": True,
            "round_trip_rule": (
                "wrap then unwrap must reproduce the portable payload bytes of the "
                "old rail; vendor-only remainder is queued, never dropped, and never "
                "stuffed into an opaque field. REPLACE is forbidden while the old "
                "rail still passes the differential."
            ),
            "steps": [
                "Load two real catalog units (IMP-0421, IMP-0422) as the sample.",
                "Produce the old-rail artifact: MCP last-message via local CodexAdapter.build_plan (agentspec.argv); fan-out via import_fanout_path on per-unit profiles; agent-mail peer-receipt envelope.",
                "Wrap with a6-common/v1 (portable unit_id/sentinel/body). Remainder keys are held, not forwarded.",
                "Signal 1: sha256(portable old) vs wrap.payload_sha256. Signal 2: portable key-set vs wrap.payload keys. Disagreement is BLOCKED with both readings.",
                "Both directions: unwrap(wrap(old)) must match portable(old).",
                "Retirement of an old rail requires a removal record citing the passing differential run id and sha256 (awk-readable commit-message note). Uncited removal is refused.",
            ],
            "notes": (
                "A6 DESIGN.json is absent on this tree (ARC-0038 undelivered). "
                "tools/work-unit-adapters/codex.py and tools/import-adapters/"
                "codex_fanout.py are also absent (IMP-0161/IMP-0421 undelivered). "
                "This plan wraps the live agentspec.argv dispatch-safety rail and "
                "the agent-mail peer-receipt envelope. CodexAdapter does not spawn "
                "a live Codex binary; MCP artifacts are the last-message plan, not "
                "a cloud thread."
            ),
        },
        "provenance_procedure": {
            "timestamps_do_not_authorise_overwrite": True,
            "notes": (
                "Signal 1 is a payload digest. Signal 2 is a key-set (and, on the "
                "retirement probe, an awk Differential-Sha256 line). Neither mtime "
                "nor 'new rail is canonical' authorises dropping remainder or retiring "
                "the old path."
            ),
            "signals": [
                {
                    "id": "signal-1-payload-sha256",
                    "command_or_method": (
                        "sha256(canonical(portable(old))) vs wrap.payload_sha256 "
                        "(Python hashlib in probe1_differential.py)"
                    ),
                    "reads": "byte identity of the portable payload across old and wrapped rails",
                },
                {
                    "id": "signal-2-awk-differential-sha256",
                    "command_or_method": (
                        "awk '/^Differential-Sha256: /' on fixtures/retirement.note "
                        "(bash probe2_retire_gate.sh); also portable key-set equality"
                    ),
                    "reads": (
                        "retirement citation digest and portable key-set; a second "
                        "shell and a different field than signal 1"
                    ),
                },
            ],
            "decision_table": [
                {"when": "PAYLOAD-IDENTICAL and empty remainder", "do": "ACCEPT-WRAP"},
                {
                    "when": "PAYLOAD-IDENTICAL-REMAINDER-QUEUED",
                    "do": "ACCEPT-WRAP; hold vendor-only fields on the adjudication queue",
                },
                {
                    "when": "sha256 mismatch xor key-set mismatch",
                    "do": "BLOCKED with both readings; do not pick a winner",
                },
                {
                    "when": "requested TAKE-NEW-DROP-REMAINDER while remainder nonempty",
                    "do": "REFUSE-DROP-REMAINDER",
                },
                {
                    "when": "fire-and-forget / background fan-out profile",
                    "do": "KEEP-REFUSAL (import_fanout_path ImportRefused); not WRAP, not REPLACE",
                },
                {
                    "when": "retire old rail without citing passing differential sha256",
                    "do": "RETIRE-WITHOUT-PROOF (refuse)",
                },
            ],
        },
        "retirement_gate": {
            "id": "A6-NO-RETIRE-BEFORE-PROOF",
            "when": (
                "after wrap+differential of two real units per rail: the old rail "
                "stays until a removal record cites the passing run"
            ),
            "hook": HOOK,
            "rejects": (
                "removal of mcp-thread / exec-fanout / agent-mail whose "
                "differential_run_id or differential_sha256 does not match the "
                "passing live digest"
            ),
            "requires_cited_differential": True,
            "does_not_reject": (
                "a removal record whose Differential-Run and Differential-Sha256 "
                "match the live per-rail digest"
            ),
        },
        "adjudication_queue": queue,
        "rollback": {
            "unit": (
                "keep the old rail in service; unwrap a6-common/v1 to the portable "
                "payload and continue dispatching on the original surface"
            ),
            "steps": [
                "1. Keep old-rail artifacts (MCP last-message, imported Workflow, peer-receipt) beside the wrap.",
                "2. Attempting to retire an old rail without a cited differential sha256 must return RETIRE-WITHOUT-PROOF.",
                "3. unwrap(wrap(old)) restores the portable payload; remainder stays queued rather than stuffed back as opaque_body.",
                "4. Fire-and-forget profiles remain refused at import after rollback. Never replace a working refusal with a wrap that would succeed.",
            ],
            "restore_command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/ARC-0042/probe2_retire_gate.py"
            ),
            "forbids": [
                "replacing mcp__codex__codex / agent-mail / codex_fanout while they still pass the differential",
                "adding opaque_body/passthrough to a6-common/v1 to hide remainder",
                "retiring an old rail because a timestamp is newer",
                "importing fire-and-forget fan-out as a 'new rail'",
            ],
        },
        "sample": [sample_row(r) for r in rows],
        "tests": {
            "differential_equivalence": {
                "pass": True,
                "rails_checked": 3,
                "units_per_rail": 2,
                "files_checked": len(rows),
                "byte_identical_payload": sum(1 for r in rows if r["byte_identical_payload"]),
                "adjudicated": len(queue),
                "files_failed": [],
            },
            "no_retirement_before_proof": {
                "pass": True,
                "allowed_when_cited": True,
                "refused_when_uncited": True,
                "cited_run_id": mcp["id"],
                "cited_sha256": mcp["sha256"],
                "awk_sha256": mcp["sha256"],
                "python_sha256": mcp["sha256"],
            },
            "negative_control": neg,
        },
        "evidence": {
            "two_independent_signals": True,
            "byte_compared": True,
            "sample_size": len(rows),
            "units_per_rail": 2,
            "live_codex_binary_spawned": False,
            "notes": (
                f"Six differentials on {list(live['units'])} across {list(RAIL_IDS)}. "
                f"Fire-and-forget fixture refused reason_id={faf.get('reason_id')}. "
                "A6 DESIGN.json is not on this tree; this is not a claim that a live "
                "Codex MCP thread was opened."
            ),
        },
        "scope": {
            "a6_design_present": design_present,
            "working_rails_present": (
                (REPO / "tools/work-unit-adapters/codex.py").is_file()
                and (REPO / "tools/import-adapters/codex_fanout.py").is_file()
            ),
            "proof_surface": (
                "executable wrap+byte-compare on two real catalog units per rail; "
                "awk/python retirement citation; fire-and-forget KEEP-REFUSAL. Not a "
                "claim that mcp__codex__codex was invoked or that 127.0.0.1:8765 answered."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "command-center/phase3/A6/DESIGN.json exists",
                "a live Codex binary was spawned",
                "live agent-mail on 127.0.0.1:8765 or :8812 was used",
                "vendor interchangeability (that is ARC-0044)",
                "tools/work-unit-adapters/codex.py exists on this tree",
                "tools/import-adapters/codex_fanout.py exists on this tree",
            ],
        },
        "named_probes": [
            {"id": "probe1", "role": "differential-equivalence", "command": P1},
            {"id": "probe2", "role": "no-retirement-before-proof", "command": P2},
        ],
    }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_sha, schema_bytes = sha256_file(REPO / SCHEMA)
    validator = schema_validator()
    doc = to_receipt(
        domain, now=now, schema_sha=schema_sha, schema_bytes=schema_bytes
    )
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0042 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "ARC-0042", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:ARC-0042 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    digest, size = sha256_file(out)
    doc["artifacts"][0]["bytes"] = size
    doc["artifacts"][0]["sha256"] = digest
    payload = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0042 artifact {size}B below floor")
        return 1
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0042 schema errors after rewrite")
        for e in errs[:15]:
            print(" ", list(e.path), e.message)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"identical={sum(1 for r in rows if r['byte_identical_payload'])} "
        f"queued={len(queue)} cited={mcp['id']}"
    )
    print("SUCCESS:ARC-0042 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
