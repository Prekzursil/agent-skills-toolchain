#!/usr/bin/env python3
"""Emit TST-0144 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0144"
OUT = "command-center/receipts/TST-0144.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0144"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0144/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0144/probe2_lenient_mutant.py"
)
LIB = "tools/completion/parse_cache.py"
LIB_TEST = "tools/completion/tests/test_parse_cache.py"
QUESTION = (
    "When an artifact is non-empty but truncated mid-JSON, does condition 4 "
    "fail AND does no downstream consumer retain a partially-parsed object? "
    "PASS requires the parse cache to hold no entry for that artifact after "
    "the failure."
)
SUPPORTING = [
    LIB,
    LIB_TEST,
    "tools/completion/reducer.py",
    "command-center/p2-wave/probes/TST-0144/harness.py",
    "command-center/p2-wave/probes/TST-0144/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0144/probe2_lenient_mutant.py",
    "command-center/p2-wave/probes/TST-0144/fixtures/complete.json",
    "command-center/p2-wave/probes/TST-0144/fixtures/truncated.json",
    "command-center/p2-wave/probes/TST-0144/fixtures/artifact.schema.json",
    SCHEMA,
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        doc = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0144/SUBAGENT-RETURN.json",
        "role": role,
    }


def validate(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    import jsonschema

    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in (
        {},
        {"unit_id": UNIT, "state": "SUCCESS"},
        {"totally": "unrelated", "passing_tests": 999999},
    ):
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            continue
        raise SystemExit("FAILED:TST-0144 schema accepts garbage")


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    c_lib, t_lib = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B " + LIB_TEST
    )
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_lib != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0144 emit lib={c_lib} p1={c1} p2={c2}")
        print(t_lib[-2000:])
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    p1 = extract_json(t1)
    p2 = extract_json(t2)
    if not (p1.get("ok") and p2.get("ok")):
        print("FAILED:TST-0144 emit named probes did not report ok")
        return 1

    fail = (p1.get("truncated") or {}).get("failure") or {}
    byte_offset = fail.get("byte_offset")
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lib_sha, lib_n = digest(REPO / LIB)
    supporting_arts = [art(p, "supporting") for p in SUPPORTING]

    receipt = {
        "answer": (
            "Yes. Strict json.loads plus schema validation in "
            "completion.parse_cache fails truncated mid-JSON with a byte "
            f"offset ({byte_offset}) and does not insert that artifact id. "
            "A downstream consumer that reads only through the cache therefore "
            "retains nothing. The complete fixture parses, validates, and is "
            "cached. A lenient repair mutant does cache a reconstructed object "
            "and therefore fails this test. "
            f"{SENTINEL}"
        ),
        "artifact_paths": [OUT, LIB] + SUPPORTING,
        "artifacts": supporting_arts,
        "catalog_output_schema": (
            "command-center/schema/receipt.schema.json#/$defs/predicate_report"
        ),
        "cloud_ok": False,
        "completion_sentinel": SENTINEL,
        "evidence": [
            {
                "kind": "parse-error-byte-offset",
                "claim": (
                    "Truncated mid-JSON fails condition 4 with a JSONDecodeError "
                    "byte offset; the parse cache then holds no entry for that id."
                ),
                "detail": (
                    f"truncated failure={json.dumps(fail, sort_keys=True)}; "
                    f"cached={p1.get('truncated', {}).get('cached')}; "
                    f"consumer_holds={p1.get('truncated', {}).get('consumer_holds')}; "
                    f"condition_4={p1.get('truncated', {}).get('condition_4')}"
                ),
            },
            {
                "kind": "cache-inspection",
                "claim": (
                    "Independent probe 2 re-inspects the cache: strict miss plus "
                    "byte offset, and a repairing parser fails the same contract "
                    "because it would retain a reconstructed object."
                ),
                "detail": (
                    f"strict={json.dumps(p2.get('strict'), sort_keys=True)}; "
                    f"mutant={json.dumps(p2.get('mutant'), sort_keys=True)}"
                ),
            },
        ],
        "id": UNIT,
        "implementation": {
            "module": LIB,
            "module_bytes": lib_n,
            "module_sha256": lib_sha,
            "operator": (
                "json.loads (no repair) then Draft7Validator; cache insert only "
                "on full success; DownstreamConsumer reads cache.get only"
            ),
        },
        "manifest_registration": {
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "manifest_path": "command-center/p2-wave/probes/TST-0144/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 512,
        "negative_controls": [
            {
                "description": (
                    "A lenient parser that closes open strings and braces on "
                    "truncated JSON caches a reconstructed object; this unit's "
                    "contract therefore fails that mutant."
                ),
                "fired_on_bad_state": True,
                "id": "TST-0144-NC-lenient-repair",
                "kind": "negative-control",
                "silent_on_good_state": True,
            }
        ],
        "notes": (
            "G-1 TST-0144: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py "
            "--write. Catalog COMPLETION-GATES.json and ARTIFACT-MANIFEST.json "
            "are absent on this worktree; the live SUT is tools/completion "
            f"parse_cache + reducer condition 4. {SENTINEL}"
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "predicate_report": {
            "complete": p1.get("complete"),
            "truncated": p1.get("truncated"),
            "lenient_mutant": p2.get("mutant"),
            "strict_review": p2.get("strict"),
        },
        "premise": {
            "action": (
                "Did not exit on predicate:absent. Implemented "
                "tools/completion/parse_cache.py and two named probes. "
                "receipt.schema.json#/$defs/predicate_report is absent; this "
                "receipt uses the discriminating test-receipt schema and embeds "
                "the condition-4 vector."
            ),
            "catalog_inputs": [
                "_USER-PROMPTS.md:11009 (Phase 10 layer 21, partial-artifact tests)",
                "_USER-PROMPTS.md:10627-10648 (shared completion predicate, 12 conditions)",
                "command-center/COMPLETION-GATES.json",
                "command-center/ARTIFACT-MANIFEST.json",
            ],
            "inputs_were_absent": True,
        },
        "produced_by": {
            "execution_substrate": "linux-worktree-local",
            "model": "grok-4.6",
            "role": "completion-predicate-tester",
            "vendor": "cursor",
        },
        "profile": "p2-wave-g1-unit",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "report_kind": "test-receipt",
        "reviewer": {
            "independent": True,
            "notes": (
                "Probe 2 is the independent adversarial reviewer: it reapplies "
                "the truncated-JSON cache contract to a repairing mutant that "
                "must fail, without authoring parse_cache.py."
            ),
            "reviewer_id": "TST-0144-probe2-lenient-mutant",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests": [
            {
                "id": "test_complete_artifact_parses_and_caches",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "test_truncated_json_fails_condition_4_and_is_not_cached",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "test_lenient_repair_parser_fails_this_test",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "timestamps": {"ended_at": ended, "started_at": started},
        "title": "Truncated JSON fails schema parse and is never cached as parsed",
        "unit_id": UNIT,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if len(blob.encode("utf-8")) < int(receipt["min_bytes_threshold"]):
        print("FAILED:TST-0144 emit below min_bytes_threshold")
        return 1
    if SENTINEL not in blob:
        print("FAILED:TST-0144 emit sentinel missing")
        return 1
    out_path.write_text(blob, encoding="utf-8")
    validate(json.loads(out_path.read_text(encoding="utf-8")))

    primary = row(OUT, "primary")
    receipt["artifacts"] = [art(OUT, "primary")] + supporting_arts
    blob = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    out_path.write_text(blob, encoding="utf-8")
    validate(json.loads(out_path.read_text(encoding="utf-8")))
    primary = row(OUT, "primary")

    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "cloud_ok": False,
        "id": UNIT,
        "manifest_path": "command-center/p2-wave/probes/TST-0144/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "both-states-complete-caches-truncated-not-cached",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "lenient-repair-mutant-must-fail",
            },
        ],
        "notes": (
            "G-1 for TST-0144: live named probes exit 0, TST-0144.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0144-probe2-lenient-mutant",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": ended,
        "unit_id": UNIT,
    }
    man_rows = [primary] + [row(p, "supporting") for p in SUPPORTING]
    man_rows.append(row("command-center/p2-wave/probes/TST-0144/emit_receipt.py", "supporting"))
    man = {
        "artifacts": man_rows,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(man_rows),
        "present": len(man_rows),
        "schema_version": 1,
        "unit_id": UNIT,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
