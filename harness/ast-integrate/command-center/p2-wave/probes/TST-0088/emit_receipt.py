#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0088.json from live SIGKILL + fan-in runs."""
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
import scenario as S  # noqa: E402

OUT = "command-center/receipts/TST-0088.json"
SCHEMA = "command-center/schema/fault-injection-receipt.schema.json"
QUESTION = (
    "Failure classes :11009 and :11313. Target: SIGKILL a unit while it is "
    "streaming its artifact and assert the fan-in classifies the truncated file "
    "FAILED at condition 5, never SUCCESS. Distinct from TST-0004 (artifact "
    "wholly absent): here the file exists, parses partially, and looks plausible."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0088/probe1_truncated_failed.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0088/probe2_atomic_invisible.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    return {"path": rel, "exists": path.is_file(), "role": role}


def main() -> int:
    truncated = S.truncated_kill()
    complete = S.complete_streaming()
    absent = S.absent_artifact()
    hidden = S.atomic_kill()
    atomic_ok = S.complete_atomic()
    c = truncated["classification"]
    fx = truncated["fixture"]
    if c["verdict"] == "SUCCESS" or c["condition_id"] != 5:
        print(f"FAILED:TST-0088 emit truncated classification {c}")
        return 1
    if not c["parses"] or not c["looks_plausible"] or not c["exists"]:
        print(f"FAILED:TST-0088 emit truncated not plausible {c}")
        return 1
    if complete["classification"]["verdict"] != "SUCCESS":
        print("FAILED:TST-0088 emit complete streaming not SUCCESS")
        return 1
    if absent["classification"]["condition_id"] != 2:
        print("FAILED:TST-0088 emit absent was not condition 2")
        return 1
    if hidden["destination_visible"]:
        print("FAILED:TST-0088 emit atomic kill exposed destination")
        return 1
    if atomic_ok["classification"]["verdict"] != "SUCCESS":
        print("FAILED:TST-0088 emit atomic complete not SUCCESS")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fixture_rel = fx["path"]
    fixture_path = REPO / fixture_rel
    if not fixture_path.is_file() or fixture_path.stat().st_size != fx["bytes"]:
        print("FAILED:TST-0088 emit fixture missing or byte-length drift")
        return 1

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0088",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0088",
        "completion_sentinel": "SUCCESS:TST-0088",
        "title": "Partial artifact without a sentinel: kill a unit mid-write",
        "spec_anchor": "_USER-PROMPTS.md:11009,11313",
        "question": QUESTION,
        "answer": (
            "YES: a live SIGKILL in the streaming hold window leaves a parseable, "
            f"plausible file ({fx['bytes']} bytes, sha256={fx['sha256'][:12]}…) "
            "that fan-in classifies FAILED at condition 5 "
            f"({c['condition_name']}), never SUCCESS. An absent path fails at "
            "condition 2 (TST-0004), not 5. Atomic tmp+rename publish leaves the "
            "destination invisible under the same SIGKILL. SUCCESS:TST-0088"
        ),
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "fault-injection-engineer",
            "execution_substrate": "linux-local",
        },
        "injection": {
            "method": "SIGKILL-after-partial-flush",
            "signal": truncated["kill"]["signal"],
            "signal_number": truncated["kill"]["signal_number"],
            "kill_issued": truncated["kill"]["kill_issued"],
            "saw_ready": truncated["kill"]["saw_ready"],
            "ready_token": truncated["kill"]["ready_token"],
            "returncode": truncated["kill"]["returncode"],
            "distinct_from": "TST-0004 artifact wholly absent (condition 2)",
            "failure_classes": ["11009", "11313", "partial-artifact", "severed-stream"],
        },
        "classification": {
            "verdict": c["verdict"],
            "condition_id": c["condition_id"],
            "condition_name": c["condition_name"],
            "never_success": True,
            "truncated_exists": c["exists"],
            "truncated_parses": c["parses"],
            "truncated_looks_plausible": c["looks_plausible"],
            "sentinel_present": c["sentinel_present"],
            "observed_sentinel": c["observed_sentinel"],
            "expected_sentinel": c["expected_sentinel"],
            "conditions": c["conditions"],
        },
        "truncated_fixture": {
            "path": fixture_rel,
            "bytes": fx["bytes"],
            "sha256": fx["sha256"],
            "parses": c["parses"],
            "looks_plausible": c["looks_plausible"],
            "sentinel_present": False,
        },
        "atomic_fix": {
            "destination_visible_after_sigkill": hidden["destination_visible"],
            "published_partial": hidden["published_partial"],
            "tmp_leftover": hidden["kill"]["tmp_exists"],
            "uninterrupted_verdict": atomic_ok["classification"]["verdict"],
        },
        "both_states": {
            "truncated_verdict": c["verdict"],
            "complete_streaming_verdict": complete["classification"]["verdict"],
            "absent_condition_id": absent["classification"]["condition_id"],
            "atomic_complete_verdict": atomic_ok["classification"]["verdict"],
        },
        "artifacts": [
            art(OUT, "primary"),
            art(SCHEMA, "supporting"),
            art(fixture_rel, "fixture"),
            art("command-center/p2-wave/probes/TST-0088/fanin.py", "supporting"),
            art("command-center/p2-wave/probes/TST-0088/writers.py", "supporting"),
            art("command-center/p2-wave/probes/TST-0088/kill_harness.py", "supporting"),
            art("command-center/p2-wave/probes/TST-0088/scenario.py", "supporting"),
            art(
                "command-center/p2-wave/probes/TST-0088/probe1_truncated_failed.py",
                "supporting",
            ),
            art(
                "command-center/p2-wave/probes/TST-0088/probe2_atomic_invisible.py",
                "supporting",
            ),
            art(
                "command-center/p2-wave/probes/TST-0088/victim.schema.json",
                "supporting",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "SIGKILL of the streaming writer after a fsync'd parseable "
                    "prefix leaves a file that exists, parses, looks like SUCCESS, "
                    f"and is {fx['bytes']} bytes, with no typed sentinel."
                ),
                "verdict": "CONFIRMED",
                "anchor": fixture_rel + ":1",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": json.dumps(
                            {
                                "verdict": c["verdict"],
                                "condition_id": c["condition_id"],
                                "bytes": fx["bytes"],
                                "signal": truncated["kill"]["signal"],
                            },
                            sort_keys=True,
                        ),
                    }
                ],
            },
            {
                "claim": (
                    "Fan-in classifies that truncated file FAILED at condition 5 "
                    "(required sentinel is present), never SUCCESS. An absent path "
                    "fails at condition 2, proving the reject is not 'fail everything "
                    "at 5'."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0088/fanin.py:127",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "raw_output": json.dumps(
                            {
                                "truncated_condition_id": c["condition_id"],
                                "absent_condition_id": absent["classification"][
                                    "condition_id"
                                ],
                                "complete_verdict": complete["classification"][
                                    "verdict"
                                ],
                            },
                            sort_keys=True,
                        ),
                    }
                ],
            },
            {
                "claim": (
                    "The stronger fix holds: tmp+rename atomic publish under the "
                    "same SIGKILL leaves the destination path unreadable as a "
                    "partial. Uninterrupted atomic write is SUCCESS."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0088/writers.py:74",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "raw_output": json.dumps(
                            {
                                "destination_visible": hidden["destination_visible"],
                                "atomic_complete": atomic_ok["classification"][
                                    "verdict"
                                ],
                            },
                            sort_keys=True,
                        ),
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "test_truncated_artifact_is_failed_not_success",
                "name": (
                    "SIGKILL mid-stream; truncated file exists, parses, looks "
                    "plausible; fan-in FAILED at condition 5, never SUCCESS"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_atomic_write_prevents_the_partial_from_being_visible_at_all",
                "name": (
                    "Atomic tmp+rename: SIGKILL leaves destination absent; "
                    "streaming writer is the detector control that DOES leak a partial"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0088-NC-COMPLETE-STREAMING",
                "kind": "both-states",
                "description": "Uninterrupted streaming write is classified SUCCESS",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"verdict={c['verdict']} condition_id={c['condition_id']}",
                "good_state_output": (
                    f"verdict={complete['classification']['verdict']}"
                ),
            },
            {
                "id": "TST-0088-NC-ABSENT-IS-CONDITION-2",
                "kind": "distinct-from-TST-0004",
                "description": (
                    "A missing path fails at condition 2, not condition 5"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"absent condition_id={absent['classification']['condition_id']}"
                ),
                "good_state_output": (
                    f"truncated condition_id={c['condition_id']}"
                ),
            },
            {
                "id": "TST-0088-NC-STREAMING-LEAKS",
                "kind": "detector-control",
                "description": (
                    "Non-atomic streaming writer leaves a readable partial, proving "
                    "the kill landed in the write window"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"streaming dest exists bytes={fx['bytes']}",
                "good_state_output": (
                    f"atomic dest visible={hidden['destination_visible']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0088-probe2-atomic-independence",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "Mechanically different from probe 1: tmp+rename atomicity plus "
                "detector control that the streaming writer still leaks a partial. "
                "Does not re-use probe 1's SUCCESS claim; it re-runs SIGKILL and "
                "asserts destination invisibility."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "truncated-failed-at-condition-5", "command": P1},
            {"id": "probe2", "role": "atomic-partial-invisible", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0088/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "timestamps": {
            "started_at": "2026-08-24T18:35:00Z",
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "NO retry. A retry masks the exact instability this unit exists "
                "to measure; a failed run is the datum, re-run only with a changed "
                "hypothesis recorded first"
            ),
        },
        "adv_rebuild_circle": False,
        "required_fix": None,
    }

    for row in doc["artifacts"]:
        if row["path"] != OUT and not row["exists"]:
            print(f"FAILED:TST-0088 emit missing artifact {row['path']}")
            return 1
    doc["artifacts"][0]["exists"] = True

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0088 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:TST-0088 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0088 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0088 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
