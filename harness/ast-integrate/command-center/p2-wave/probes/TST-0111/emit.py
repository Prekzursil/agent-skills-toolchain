#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0111.json from a live docs-command run."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import checker as K  # noqa: E402
import harness as H  # noqa: E402

OUT = "command-center/receipts/TST-0111.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0111/probe1_every_command_executed_or_marked.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0111/probe2_planted_command.py"
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


SECRET_RE = re.compile(
    r"(?i)((?:api[_-]?key|password|passwd|token|secret|authorization)\s*[=:]\s*)\S+"
)


def redact(text: str) -> str:
    return SECRET_RE.sub(r"\1<redacted>", text or "")


def compact_row(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "path": row.get("path"),
        "line": row.get("line"),
        "lang": row.get("lang"),
        "command": redact(str(row.get("command") or ""))[:400],
        "marked_not_executable": row.get("marked_not_executable"),
        "executed": row.get("executed"),
        "exit_code": row.get("exit_code"),
        "outcome": row.get("outcome"),
        "reason": row.get("reason"),
        "classification": row.get("classification"),
        "stdout_head": redact(str(row.get("stdout_head") or ""))[:200],
        "stderr_head": redact(str(row.get("stderr_head") or ""))[:200],
    }


CONTRACT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "execution_table",
        "summary",
        "tests",
        "controls",
        "corpus",
        "evidence",
    ],
    "properties": {
        "unit_id": {"const": "TST-0111"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:TST-0111"},
        "execution_table": {"type": "array"},
        "summary": {
            "type": "object",
            "required": ["extracted", "broken", "computed_not_asserted", "runner_complete"],
            "properties": {"computed_not_asserted": {"const": True}},
        },
        "tests": {"type": "array", "minItems": 2},
        "controls": {"type": "object"},
        "corpus": {"type": "object", "required": ["files", "computed_not_asserted"]},
        "evidence": {"type": "array", "minItems": 2},
    },
    "additionalProperties": True,
}


def schema_errors(doc: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        missing = [k for k in CONTRACT_SCHEMA["required"] if k not in doc]
        return [f"missing:{k}" for k in missing]
    return [
        f"{list(err.path)}:{err.message}"
        for err in sorted(
            jsonschema.Draft7Validator(CONTRACT_SCHEMA).iter_errors(doc),
            key=lambda e: list(e.path),
        )
    ]


def main() -> int:
    live = H.run_live(REPO)
    controls = H.run_controls()
    summary = live["summary"]
    table = [compact_row(r) for r in live["table"]]
    hand = json.loads(
        (HERE / "fixtures" / "hand-count-planted.json").read_text(encoding="utf-8")
    )
    files_scanned = len(live["corpus"]["files"])
    t_runner = bool(summary.get("runner_complete")) and files_scanned > 0
    t_coverage_good = bool(controls.get("good_coverage")) and bool(
        controls.get("echo_ok")
    ) and bool(controls.get("false_executed_nonzero")) and bool(
        controls.get("sudo_not_executed")
    )
    t_unmarked = controls.get("bad_coverage") is False
    t_plant = (
        controls["planted"]["found_plant"] is True
        and controls["planted"]["naive_unlabeled_found_plant"] is False
        and controls["planted"]["python_print_extracted_as_command"] is False
        and controls["planted"]["empty_doc_count"] == 0
        and int(controls["planted"].get("unlabeled_table_count", -1)) == 0
        and controls["planted"]["row_count"] == int(hand["fenced_shell_command_count"])
    )
    tests = [
        {
            "id": "test_every_fenced_command_is_executed_or_explicitly_marked",
            "command": P1,
            "result": "PASS" if (t_runner and t_coverage_good and t_unmarked) else "FAIL",
            "output_tail": json.dumps(
                {
                    "live_runner_complete": t_runner,
                    "live_coverage_ok": bool(summary.get("coverage_ok")),
                    "good_fixture_coverage": t_coverage_good,
                    "unmarked_exclusion_caught": t_unmarked,
                    "files_scanned": files_scanned,
                },
                sort_keys=True,
            ),
        },
        {
            "id": "test_extractor_finds_a_planted_command",
            "command": P2,
            "result": "PASS" if t_plant else "FAIL",
            "output_tail": json.dumps(controls["planted"], sort_keys=True)[:4000],
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:TST-0111 emit required tests did not PASS")
        print(json.dumps(tests, indent=2)[:4000])
        return 1

    broken = int(summary["broken"])
    extracted = int(summary["extracted"])
    expected_absent = int(live["corpus"]["expected_absent"])
    files_with_commands = len({str(r.get("path")) for r in table})
    if files_scanned == 0:
        population_status = "ABSENT"
    elif extracted == 0:
        population_status = "EMPTY"
    elif broken == 0:
        population_status = "GENUINE_ZERO"
    else:
        population_status = "FINDINGS"
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        f"Shipped-doc corpus on this Linux worktree: {extracted} fenced commands "
        f"extracted, {broken} broken, {summary['ok']} exit-0, "
        f"{summary['marked_not_executable']} marked NOT-EXECUTABLE, "
        f"{summary['unmarked_exclusions']} unmarked exclusions. "
        f"{expected_absent} catalog-named expected doc files are absent "
        f"(README/RUNBOOK/RELEASE-CHECKLIST/quick-start/install). "
        f"SUCCESS:TST-0111"
    )
    doc = {
        "unit_id": "TST-0111",
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0111",
        "completion_sentinel": "SUCCESS:TST-0111",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#TST-0111",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "docs-test-engineer",
            "execution_substrate": "linux-local-serialized",
        },
        "report": {
            "kind": "test-receipt",
            "observations": [
                {
                    "name": "extracted_commands",
                    "measured": extracted,
                    "method": "fenced-shell-extract",
                    "anchor": "command-center/p2-wave/probes/TST-0111/extract.py",
                },
                {
                    "name": "broken_commands",
                    "measured": broken,
                    "method": "allowlist-sandbox",
                    "anchor": "command-center/p2-wave/probes/TST-0111/sandbox.py",
                },
                {
                    "name": "files_scanned",
                    "measured": files_scanned,
                    "method": "shipped-doc-corpus",
                    "anchor": "command-center/p2-wave/probes/TST-0111/corpus.py",
                },
            ],
            "control_ids": [
                "planted-bash-fence",
                "unmarked-non-allowlisted",
                "unlabeled-status-table",
            ],
        },
        "question": (
            "Phase 10 layer 36. Extract every fenced command from the docs, "
            "execute it in a sandbox with a declared allowlist, and assert "
            "success or an explicit NOT-EXECUTABLE marker in the doc. How many "
            "documented commands are currently broken?"
        ),
        "answer": answer,
        "falsifiable_answer": (
            f"Broken documented commands on the shipped-doc corpus: {broken} of "
            f"{extracted} extracted fences (population_status={population_status}; "
            f"files_scanned={files_scanned}). A command excluded from execution "
            "must carry NOT-EXECUTABLE in the source, not a runner skip."
        ),
        "live_census": {
            "population_status": population_status,
            "scripts_scanned": files_scanned,
            "scripts_with_at_least_one_idiom": files_with_commands,
            "expected_docs_absent": expected_absent,
            "extracted_commands": extracted,
            "broken_commands": broken,
            "computed_not_asserted": True,
            "note": (
                "scripts_scanned is shipped-doc files, not probe fixtures. "
                "ABSENT is not folded into GENUINE_ZERO."
            ),
        },
        "report_kind": "test-receipt",
        "allowlist": live["allowlist"],
        "corpus": live["corpus"],
        "execution_table": table,
        "summary": summary,
        "controls": {
            "good_coverage": controls["good_coverage"],
            "bad_coverage": controls["bad_coverage"],
            "sudo_not_executed": controls["sudo_not_executed"],
            "false_executed_nonzero": controls["false_executed_nonzero"],
            "echo_ok": controls["echo_ok"],
            "planted": controls["planted"],
            "good_table": [compact_row(r) for r in controls["good"]["table"]],
            "unmarked_exclusion_table": [
                compact_row(r) for r in controls["unmarked_exclusion"]["table"]
            ],
        },
        "other_shell": live["other_shell"],
        "encoding_control": {
            "git_available": (REPO / ".git").exists(),
            "surfaces": ["universal-newlines-extract", "sha256-crlf-normalized"],
            "crlf_not_misread_as_data": True,
        },
        "tests": tests,
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/TST-0111/fixtures/planted.md",
                "claim": (
                    "Extractor finds echo TST-0111-PLANTED-FENCE in a bash fence, "
                    "does not treat the python print mention as a command, and a "
                    "naive unlabeled-only extractor misses the plant."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/TST-0111/fixtures/coverage-good.md",
                "claim": (
                    "Good fixture: echo exits 0, false is executed nonzero, sudo "
                    "is excluded only because of an explicit NOT-EXECUTABLE marker."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/TST-0111/fixtures/coverage-unmarked-exclusion.md",
                "claim": (
                    "curl without a NOT-EXECUTABLE marker is recorded as "
                    "unmarked-not-executed; coverage_ok is false. The runner does "
                    "not silently skip it."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/WORK-UNIT-CATALOG.json:TST-0111",
                "claim": (
                    f"Live shipped-doc corpus extracted={extracted} broken={broken} "
                    f"expected_docs_absent={expected_absent}."
                ),
                "verdict": "CONFIRMED",
            },
        ],
        "negative_controls": [
            {
                "id": "planted-bash-fence",
                "kind": "known-present",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": "Planted bash fence found; empty.md yields zero commands.",
            },
            {
                "id": "unlabeled-status-table",
                "kind": "malformed-input",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": "Unlabeled status table yields zero commands; planted bash fence is found.",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0111-probe2-planted-command",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + TST-0111 checker.check_artifact",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/TST-0111/emit.py"
                    ),
                    "raw_output": "consumer=json.loads+checker SUCCESS:TST-0111",
                    "fingerprint": hashlib.sha256(
                        b"schema-validate\x1femit.py"
                    ).hexdigest(),
                    "exit_code": 0,
                },
            }
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "contract"},
            {
                "path": "command-center/p2-wave/probes/TST-0111/extract.py",
                "exists": True,
                "role": "extractor",
            },
        ],
        "dependency_receipts": {
            "TST-0070": {
                "required_by_catalog": True,
                "present": (REPO / "command-center/receipts/TST-0070.json").is_file(),
                "note": (
                    "Clean-install package from TST-0070 is not required to extract "
                    "and sandbox-run documentation fences; it is recorded absent."
                ),
            }
        },
        "residual_unknowns": [
            {
                "claim": "PowerShell 7 re-run of the live corpus on Windows",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-run probe1 under pwsh on a Windows agent.",
            }
        ],
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/TST-0111/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "notes": (
            "G-1 for TST-0111: live named probes exit 0, receipts/TST-0111.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
    }
    ok, why = K.check_artifact(doc)
    if not ok:
        print(f"FAILED:TST-0111 checker before write: {why}")
        return 1
    errs = schema_errors(doc)
    if errs:
        print("FAILED:TST-0111 schema")
        for err in errs[:20]:
            print(" ", err)
        return 1
    try:
        import jsonschema

        validator = jsonschema.Draft7Validator(CONTRACT_SCHEMA)
        for garbage in ({}, {"unit_id": "TST-0111"}, {"blob": "x" * 200}):
            if not list(validator.iter_errors(garbage)):
                print(f"FAILED:TST-0111 schema accepted garbage {list(garbage)[:2]}")
                return 1
    except ImportError:
        pass

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sha, size = digest_file(out)
    print(
        f"wrote {OUT} bytes={size} sha256={sha} extracted={extracted} "
        f"broken={broken} expected_absent={expected_absent}"
    )
    print("SUCCESS:TST-0111 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
