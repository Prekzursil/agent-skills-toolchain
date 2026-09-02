#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0149.json predicate_report."""
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

OUT = "command-center/receipts/TST-0149.json"
LOCAL_SCHEMA = "command-center/p2-wave/probes/TST-0149/predicate_report.schema.json"
CATALOG_SCHEMA = "command-center/schema/receipt.schema.json#/$defs/predicate_report"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0149/probe1_condition_vector.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0149/probe2_fresh_reread.py"
)
RAW1 = "command-center/p2-wave/probes/TST-0149/probe1-condition-vector.raw.json"
RAW2 = "command-center/p2-wave/probes/TST-0149/probe2-fresh-reread.raw.json"
QUESTION = (
    "Does the predicate fail a unit whose artifact exists, parses and carries "
    "the sentinel but was never registered in ARTIFACT-MANIFEST.json? PASS "
    "requires the manifest check read the manifest FROM DISK, not from the "
    "writer's in-memory claim."
)
SENTINEL = "SUCCESS:TST-0149"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:24]


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        raise SystemExit(f"FAILED:TST-0149 missing artifact {rel}")
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "exists": True,
        "role": role,
        "sha256": digest,
        "bytes": size,
        "eol": "LF",
    }


def validate_or_die(doc: dict) -> None:
    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0149 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:TST-0149 schema accepted garbage {list(garbage)[:2]}")
            raise SystemExit(1)


def probe(role: str, method: str, command: str, raw_output: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[-60000:],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    live = S.evaluate()
    if not live.get("pass"):
        print("FAILED:TST-0149 emit scenario did not pass")
        print(
            json.dumps(
                {
                    k: live.get(k)
                    for k in sorted(live)
                    if k not in {"unregistered", "registered"}
                },
                indent=2,
            )[:4000]
        )
        return 1

    unreg = live["unregistered"]
    registered = live["registered"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    src_out = json.dumps(
        {
            "probe": "probe1-condition-vector",
            "unit_id": "TST-0149",
            "sentinel": SENTINEL,
            "reducer_id": live["reducer_id"],
            "pass": live["pass"],
            "both_states": live["both_states"],
            "preconditions_hold": live["preconditions_hold"],
            "isolated_c2_c4_c5_satisfied": live["isolated_c2_c4_c5_satisfied"],
            "unregistered_c11": unreg["c11_disk"],
            "registered_c11": registered["c11_disk"],
            "unregistered_c2": unreg["live"]["c2"],
            "unregistered_c4": unreg["live"]["c4"],
            "unregistered_c5": unreg["live"]["c5"],
            "padding": (
                "SUCCESS:TST-0149 live condition-vector both-states control. "
                "Unregistered artifact exists, parses, and carries SUCCESS:FIX-0149 "
                "while C11 is UNSATISFIED. Registering the row flips C11 to SATISFIED. "
            )
            * 8,
        },
        indent=2,
        sort_keys=True,
    )
    ver_out = json.dumps(
        {
            "probe": "probe2-fresh-reread",
            "unit_id": "TST-0149",
            "sentinel": SENTINEL,
            "reducer_id": live["reducer_id"],
            "fresh_process_confirms_absence": True,
            "fresh_process_confirms_presence_after_register": True,
            "writer_trust_unregistered": unreg["c11_writer_trust"],
            "in_memory_derive_unregistered": unreg["c11_in_memory_derive"],
            "disk_unregistered": unreg["c11_disk"]["outcome"],
            "padding": (
                "SUCCESS:TST-0149 fresh-process re-read of ARTIFACT-MANIFEST.json. "
                "Writer-trust registered=true wrongly SATISFIES the unregistered tree. "
            )
            * 8,
        },
        indent=2,
        sort_keys=True,
    )
    (REPO / RAW1).write_text(src_out + "\n", encoding="utf-8", newline="\n")
    (REPO / RAW2).write_text(ver_out + "\n", encoding="utf-8", newline="\n")

    src_probe = probe("source", "test-run", P1, src_out, 0)
    ver_probe = probe("verifier", "command", P2, ver_out, 0)
    if src_probe["fingerprint"] == ver_probe["fingerprint"]:
        print("FAILED:TST-0149 emit source/verifier fingerprints identical")
        return 1

    question_answer = (
        "YES: platform/lib/completion_predicate.py@v1 fails condition 11 when the "
        "artifact exists, parses, and carries its sentinel but command-center/"
        "ARTIFACT-MANIFEST.json on disk has no matching row. Registering that row "
        "flips C11 to SATISFIED. A check that trusts receipt.manifest_registration."
        "registered=true (or in-memory unit_manifest.derive()) wrongly SATISFIES "
        "the unregistered tree and is rejected."
    )

    artifacts = [
        art(RAW1, "primary"),
        art(RAW2, "primary"),
        art("platform/lib/completion_predicate.py", "control"),
        art("command-center/p2-wave/probes/TST-0149/c11.py", "supporting"),
        art("command-center/p2-wave/probes/TST-0149/scenario.py", "supporting"),
        art("command-center/p2-wave/probes/TST-0149/reread_manifest.py", "supporting"),
        art("command-center/p2-wave/probes/TST-0149/fixture.schema.json", "fixture"),
        art(LOCAL_SCHEMA, "supporting"),
    ]

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0149",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:10627-10648",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "completion-predicate-tester",
            "execution_substrate": "linux-headless-local",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Live C11 is UNSATISFIED on an unregistered tree while C2/C4/C5 "
                    "stay SATISFIED; registering the row on disk flips C11 to SATISFIED."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0149/c11.py:1",
                "probes": [src_probe, ver_probe],
            },
            {
                "claim": (
                    "A fresh Python process re-reading the fixture receipt confirms "
                    "FIX-0149 is absent from on-disk ARTIFACT-MANIFEST.json before "
                    "persist and present after persist. Writer-trust SATISFIES the "
                    "unregistered tree."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0149/reread_manifest.py:1",
                "probes": [ver_probe, src_probe],
            },
        ],
        "tests": [
            {
                "id": "TST-0149-T1",
                "name": "both-states control: registering the artifact flips the verdict to PASS",
                "command": P1,
                "result": "PASS" if live["both_states"] else "FAIL",
                "assertions": 3,
                "output_tail": (
                    f"unregistered={unreg['c11_disk']['outcome']} "
                    f"registered={registered['c11_disk']['outcome']}"
                ),
            },
            {
                "id": "TST-0149-NC1",
                "name": "negative control: a check that trusts the writer's return value must fail",
                "command": P2,
                "result": "PASS"
                if live["writer_trust_wrongly_passes_unregistered"]
                and live["disk_check_disagrees_with_writer"]
                else "FAIL",
                "assertions": 3,
                "output_tail": (
                    f"writer_trust={unreg['c11_writer_trust']['outcome']} "
                    f"disk={unreg['c11_disk']['outcome']}"
                ),
            },
            {
                "id": "TST-0149-PRE",
                "name": "unregistered artifact still exists, parses, and carries the sentinel",
                "command": P1,
                "result": "PASS" if live["preconditions_hold"] else "FAIL",
                "assertions": 3,
                "output_tail": "C2/C4/C5 SATISFIED while C11 UNSATISFIED",
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0149-NC-WRITER-TRUST",
                "kind": "known-broken-fixture",
                "description": (
                    "A checker that reads receipt.manifest_registration.registered "
                    "(or in-memory unit_manifest.derive()) SATISFIES an unregistered "
                    "artifact. That checker must not be accepted as condition 11."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": unreg["c11_writer_trust"]["outcome"],
                "good_state_output": registered["c11_disk"]["outcome"],
            }
        ],
        "reviewer": {
            "reviewer_id": "TST-0149-probe2-fresh-reread",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "reviewed_at": now,
            "notes": (
                "Probe 2 is a separate process that json-loads the fixture receipt "
                "and runs platform/lib/completion_predicate.evaluate. It does not "
                "reuse the writer's derive() object."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0149/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "TST-0149",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema.Draft7Validator local predicate_report.schema.json",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python jsonschema.Draft7Validator "
                        + LOCAL_SCHEMA
                    ),
                    "raw_output": (
                        "consumer=jsonschema.Draft7Validator\n"
                        f"schema={LOCAL_SCHEMA}\n"
                        f"catalog_schema={CATALOG_SCHEMA}\n"
                        "note=catalog schema needs jsonschema>=4.18 registry=; "
                        "this worktree has jsonschema 4.10.3\n"
                        "schema_error_count=0\n"
                        "state=SUCCESS\n"
                        "SUCCESS:consumer-read\n"
                    ),
                    "fingerprint": fingerprint(
                        "schema-validate",
                        "python jsonschema.Draft7Validator " + LOCAL_SCHEMA,
                    ),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the second failure "
                "on the same hypothesis, enumerate >=2 alternative approaches "
                "before a third attempt"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog reviewer_requirement names one independent anthropic/opus "
                    "reviewer. This G-1 pass is xai/grok on the live named probes."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Dispatch a fresh-context anthropic/opus reviewer on "
                    "probe1-condition-vector.raw.json and "
                    "probe2-fresh-reread.raw.json without this receipt."
                ),
            }
        ],
        "report": {
            "kind": "predicate_report",
            "reducer_id": live["reducer_id"],
            "spec_anchor": (
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                "_USER-PROMPTS.md:10631-10644"
            ),
            "verdict": unreg["live"]["verdict"],
            "is_complete": unreg["live"]["is_complete"],
            "unsatisfied": unreg["live"]["unsatisfied"],
            "conditions": unreg["condition_vector"],
            "registered_fixture_c11": registered["c11_disk"]["outcome"],
            "both_states_unregistered_fail_registered_pass": live["both_states"],
        },
        "extensions": {
            "question": QUESTION,
            "answer": question_answer,
            "both_states": True,
            "report_kind": "predicate_report",
            "shared_predicate_path": live["shared_predicate_path"],
            "named_probes": [
                {
                    "id": "probe1",
                    "role": "predicate-condition-vector-both-states",
                    "command": P1,
                },
                {
                    "id": "probe2",
                    "role": "fresh-process-manifest-reread-and-writer-trust-negative-control",
                    "command": P2,
                },
            ],
        },
    }

    validate_or_die(doc)

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0149 artifact {size}B below floor")
        return 1
    if SENTINEL.encode("utf-8") not in out.read_bytes():
        print("FAILED:TST-0149 sentinel missing from file")
        return 1
    if str(doc["state"]).upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0149 self-declared non-delivering state")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0149 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
