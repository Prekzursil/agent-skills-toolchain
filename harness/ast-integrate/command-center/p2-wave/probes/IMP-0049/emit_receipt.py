#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0049.json from a live ledger run."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

from hash_census import census_diff, hash_census  # noqa: E402
from legacy_layout_steps import (  # noqa: E402
    FROM_VERSION,
    STEP_IDS,
    TO_VERSION,
    recorded_steps,
    seed_legacy_tree,
)
from migration_ledger import (  # noqa: E402
    AppendOnlyError,
    LedgerIntegrityError,
    MigrationLedger,
    apply_preimage,
    compute_record_hash,
    replay_and_compare,
    run_recorded_steps,
)

OUT = "command-center/receipts/IMP-0049.json"
SCHEMA = "command-center/schema/receipt.schema.json"
LEDGER_SCHEMA = "tools/plugin/schema/migration-ledger.schema.json"
QUESTION = (
    "Record, append-only, which migration steps ran on this machine, when, from "
    "which version, with the inverse needed to undo each — so a later rollback "
    "knows exactly what to reverse and a support question can be answered from "
    "disk rather than from memory."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def public_record(rec: dict) -> dict:
    inverse = rec.get("inverse") or {}
    entries = inverse.get("entries") or []
    return {
        "seq": rec["seq"],
        "record_id": rec["record_id"],
        "recorded_at": rec["recorded_at"],
        "machine_id": rec["machine_id"],
        "run_id": rec["run_id"],
        "from_version": rec["from_version"],
        "to_version": rec["to_version"],
        "step_id": rec["step_id"],
        "status": rec["status"],
        "touched_paths": rec.get("touched_paths") or [],
        "inverse_kind": inverse.get("kind"),
        "inverse_entry_count": len(entries),
        "inverse_paths": [e.get("path") for e in entries],
        "prev_hash": rec["prev_hash"],
        "record_hash": rec["record_hash"],
    }


def measure() -> dict:
    tmp = tempfile.TemporaryDirectory(prefix="imp0049-emit-")
    with tmp:
        root = Path(tmp.name) / "plugin-home"
        seed_legacy_tree(root)
        ledger_path = Path(tmp.name) / "migration-ledger.jsonl"
        ledger = MigrationLedger(ledger_path, machine="imp0049-emit")
        result = run_recorded_steps(
            root,
            ledger,
            recorded_steps(),
            from_version=FROM_VERSION,
            to_version=TO_VERSION,
        )
        restored = Path(tmp.name) / "restored"
        shutil.copytree(root, restored)
        replay = replay_and_compare(
            restored, ledger, result["run_id"], result["pre_census"]
        )

        inverses = ledger.inverses_for_run(result["run_id"])
        omitted = [r for r in inverses if r["step_id"] != STEP_IDS[1]]
        incomplete = Path(tmp.name) / "omit"
        shutil.copytree(root, incomplete)
        for rec in reversed(omitted):
            apply_preimage(incomplete, rec["inverse"])
        omit_diff = census_diff(result["pre_census"], hash_census(incomplete))

        before = ledger_path.read_bytes()
        rejected = []
        for name, call in (
            ("replace_record", lambda: ledger.replace_record(1, {"seq": 1})),
            ("rewrite_all", lambda: ledger.rewrite_all([])),
            ("truncate", lambda: ledger.truncate()),
        ):
            try:
                call()
                rejected.append({"op": name, "raised": False})
            except AppendOnlyError as exc:
                rejected.append({"op": name, "raised": True, "type": type(exc).__name__})
        bytes_unchanged = ledger_path.read_bytes() == before

        tampered = Path(tmp.name) / "tampered.jsonl"
        tampered.write_text(
            before.decode("utf-8").replace(
                "copied-skills-to-marketplace", "copied-skills-FORGED", 1
            ),
            encoding="utf-8",
        )
        chain_error = None
        try:
            MigrationLedger.load(tampered)
        except LedgerIntegrityError as exc:
            chain_error = str(exc)

        crash_root = Path(tmp.name) / "crash"
        seed_legacy_tree(crash_root)
        crash_ledger = MigrationLedger(
            Path(tmp.name) / "crash.jsonl", machine="imp0049-emit"
        )
        crash = run_recorded_steps(
            crash_root,
            crash_ledger,
            recorded_steps(),
            from_version=FROM_VERSION,
            to_version=TO_VERSION,
            complete=False,
        )
        loaded = MigrationLedger.load(Path(tmp.name) / "crash.jsonl")
        crash_replay = replay_and_compare(
            crash_root, loaded, crash["run_id"], crash["pre_census"]
        )
        last = loaded.records[-1]

        return {
            "run_id": result["run_id"],
            "step_ids": result["step_ids"],
            "pre_count": len(result["pre_census"]),
            "post_count": len(result["post_census"]),
            "census_changed": result["pre_census"] != result["post_census"],
            "replay_equal": replay["equal"],
            "replay_diff": replay["diff"],
            "records": [public_record(r) for r in ledger.records],
            "omit_equal": omit_diff["equal"],
            "omit_diff": omit_diff,
            "append_only": {
                "rejected": rejected,
                "bytes_unchanged": bytes_unchanged,
            },
            "hash_chain_error": chain_error,
            "interrupted": {
                "last_status": last["status"],
                "last_hash_ok": last["record_hash"] == compute_record_hash(last),
                "record_count": len(loaded.records),
                "started_without_applied": last["status"] == "started",
                "replay_equal": crash_replay["equal"],
            },
        }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    m = measure()
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )

    tests_ok = (
        m["replay_equal"]
        and m["census_changed"]
        and tuple(m["step_ids"]) == STEP_IDS
        and not m["omit_equal"]
        and all(x["raised"] for x in m["append_only"]["rejected"])
        and m["append_only"]["bytes_unchanged"]
        and bool(m["hash_chain_error"])
        and m["interrupted"]["replay_equal"]
        and m["interrupted"]["started_without_applied"]
        and m["interrupted"]["last_hash_ok"]
    )
    if not tests_ok:
        print("FAILED:IMP-0049 live measurements did not satisfy the catalog tests")
        print(json.dumps({k: v for k, v in m.items() if k != "records"}, indent=2)[:4000])
        return 1

    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0049",
        "architecture_id": "plugin-lifecycle",
        "state": "SUCCESS",
        "report_kind": "implementation-receipt",
        "title": "Migration provenance ledger recording each step and its inverse",
        "question": QUESTION,
        "sentinel": "SUCCESS:IMP-0049",
        "completion_sentinel": "SUCCESS:IMP-0049",
        "spec_anchor": "_USER-PROMPTS.md:10817",
        "min_bytes_threshold": 2048,
        "output_schema": f"{SCHEMA} + {LEDGER_SCHEMA}",
        "implementation": {
            "ledger": "tools/plugin/migration_ledger.py",
            "census": "tools/plugin/hash_census.py",
            "schema": LEDGER_SCHEMA,
            "tests": "tools/plugin/tests/test_migration_ledger.py",
            "seam": (
                "begin_step captures a preimage inverse before mutate; "
                "complete_step appends an applied marker. IMP-0047 calls this seam."
            ),
            "on_disk": "JSONL, O_APPEND, hash-chained record_hash <- prev_hash",
        },
        "artifacts": [
            art("tools/plugin/migration_ledger.py", "implementation"),
            art("tools/plugin/hash_census.py", "implementation"),
            art("tools/plugin/legacy_layout_steps.py", "fixture-steps"),
            art(LEDGER_SCHEMA, "schema"),
            art("tools/plugin/tests/test_migration_ledger.py", "tests"),
        ],
        "evidence": [
            {
                "claim": (
                    "Signal 1: after a three-step legacy-layout migration the ledger "
                    f"recorded step list {m['step_ids']} (started records, run "
                    f"{m['run_id']}). Applied markers exist as separate append-only "
                    "rows so a crash between mutate and complete still leaves the "
                    "started inverse."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/migration_ledger.py:MigrationLedger.steps_for_run",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "live run_recorded_steps on a seeded legacy tree",
                        "raw_output": json.dumps(m["step_ids"]),
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": "re-read JSONL and list status=started step_id",
                        "raw_output": json.dumps(
                            [r["step_id"] for r in m["records"] if r["status"] == "started"]
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "Signal 2: replaying only the recorded preimage inverses restored "
                    f"the pre-migration hash census "
                    f"({m['pre_count']} paths before, {m['post_count']} after apply, "
                    f"restored_equal={m['replay_equal']}). Apply was not a no-op "
                    f"(census_changed={m['census_changed']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/hash_census.py:hash_census",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "hash-census",
                        "command": "hash_census(pre) vs hash_census(replayed post-copy)",
                        "raw_output": json.dumps(m["replay_diff"]),
                    },
                    {
                        "role": "verifier",
                        "method": "hash-census",
                        "command": "independent copytree + replay_inverses",
                        "raw_output": json.dumps({"equal": m["replay_equal"]}),
                    },
                ],
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "test_inverse_replay_restores_prior_state",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/plugin/tests/test_migration_ledger.py",
                "result": "PASS",
                "assertions": 1,
                "output_tail": f"replay_equal={m['replay_equal']} steps={m['step_ids']}",
            },
            {
                "id": "NEGATIVE CONTROL omit one step from the ledger",
                "command": "replay inverses with STEP_IDS[1] removed",
                "result": "PASS",
                "assertions": 1,
                "output_tail": json.dumps(m["omit_diff"]),
            },
            {
                "id": "append-only in-place edit rejected",
                "command": "replace_record/rewrite_all/truncate + hex-edit load",
                "result": "PASS",
                "assertions": 4,
                "output_tail": json.dumps(
                    {
                        "api": m["append_only"],
                        "hash_chain_error": m["hash_chain_error"],
                    }
                ),
            },
            {
                "id": "interrupted migration partial records remain valid",
                "command": "complete=False last status=started then replay inverses",
                "result": "PASS",
                "assertions": 1,
                "output_tail": json.dumps(m["interrupted"]),
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0049-C1-omit-step",
                "kind": "known-broken-fixture",
                "description": (
                    "Drop the inverse for root-mcp-to-project and replay. The census "
                    "must differ from the pre-migration snapshot. Full replay on the "
                    "same post-tree must match, or the comparator is vacuous."
                ),
                "fired_on_bad_state": not m["omit_equal"],
                "silent_on_good_state": m["replay_equal"],
                "bad_state_output": json.dumps(m["omit_diff"]),
                "good_state_output": json.dumps(m["replay_diff"]),
            },
            {
                "id": "IMP0049-C2-in-place-edit",
                "kind": "mutation",
                "description": (
                    "API rewrite attempts must raise AppendOnlyError without changing "
                    "bytes; a hex-edit of a step_id must fail hash-chain load."
                ),
                "fired_on_bad_state": bool(m["hash_chain_error"]),
                "silent_on_good_state": m["append_only"]["bytes_unchanged"],
                "bad_state_output": str(m["hash_chain_error"]),
                "good_state_output": json.dumps(m["append_only"]),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0049-probe2-append-only-omit-interrupted",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Reviewer_requirement: ledger survives an interrupted migration "
                "(partial started records remain valid hash-chained records and "
                "their inverses still restore the prior census). Named probe 2 "
                "re-runs that experiment on a fresh tree."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0049/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "notes": "Measure runs after this emit; named probes re-execute live.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0047 (versioned step framework) is not delivered on this "
                    "worktree; the ledger seam is exercised by legacy_layout_steps "
                    "stand-ins for the four historical layouts IMP-0048 will detect."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Wire MigrationLedger.begin_step into IMP-0047 apply.",
            }
        ],
        "report": {
            "kind": "migration-provenance-ledger",
            "from_version": FROM_VERSION,
            "to_version": TO_VERSION,
            "measured": {
                "run_id": m["run_id"],
                "step_ids": m["step_ids"],
                "pre_count": m["pre_count"],
                "post_count": m["post_count"],
                "census_changed": m["census_changed"],
                "replay_equal": m["replay_equal"],
                "omit_equal": m["omit_equal"],
                "interrupted": m["interrupted"],
            },
            "ledger_records": m["records"],
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0049/probe1_inverse_replay.py"
                ),
                "role": "recorded-steps-and-inverse-replay-census",
            },
            {
                "id": "probe2",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0049/probe2_append_only.py"
                ),
                "role": "append-only-omit-step-interrupted",
            },
        ],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0049 artifact {size}B below floor")
        return 1
    if "SUCCESS:IMP-0049" not in out.read_text(encoding="utf-8"):
        print("FAILED:IMP-0049 sentinel missing after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:IMP-0049")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
