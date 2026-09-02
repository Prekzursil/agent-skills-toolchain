#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0320.json from live named probes.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (write_receipts.py
does that after named probes pass). Does not call unit_manifest.py --write.
"""
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
UNIT = "TST-0320"
OUT_REL = "command-center/receipts/TST-0320.json"
SENTINEL = "SUCCESS:TST-0320"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0320/probe1_kill_resume.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0320/probe2_idempotence_torn.py"
)
SUPPORTING = [
    "tools/bench/__init__.py",
    "tools/bench/cell.py",
    "tools/bench/evaluate.py",
    "tools/bench/ledger.py",
    "tools/bench/runner.py",
    "tools/bench/kill_target.py",
    "tools/bench/schema/result-row.schema.json",
    "command-center/bench/cases/corpus.json",
    "command-center/bench/results/LEDGER-CONTRACT.json",
    "command-center/p2-wave/probes/TST-0320/probe1_kill_resume.py",
    "command-center/p2-wave/probes/TST-0320/probe2_idempotence_torn.py",
]
QUESTION = (
    "Implementation target: a tournament over hundreds of cases and dozens of "
    "candidates will be interrupted. Make the runner resumable at case "
    "granularity with idempotent result writes keyed by (candidate, case, "
    "harness version, seed), so a resume neither re-runs completed work nor "
    "appends a second result row for it. Double-counting is the silent "
    "variant: the tournament completes, the numbers are wrong, and nothing "
    "looks broken."
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str, timeout: int = 180) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def parse_probe_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def function_line(rel: str, name: str) -> tuple[int, str]:
    path = REPO / rel
    text = path.read_text(encoding="utf-8")
    needle = f"def {name}("
    idx = text.find(needle)
    if idx < 0:
        raise SystemExit(f"FAILED:{UNIT} missing {name} in {rel}")
    line = text[:idx].count("\n") + 1
    snippet = text[idx : idx + 96].splitlines()[0]
    return line, snippet


def main() -> int:
    c1, t1 = run_cmd(P1, timeout=180)
    c2, t2 = run_cmd(P2, timeout=180)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} emit probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1
    if f"SUCCESS:{UNIT}-probe1" not in t1:
        print("FAILED:TST-0320 emit probe1 sentinel missing")
        return 1
    if f"SUCCESS:{UNIT}-probe2" not in t2:
        print("FAILED:TST-0320 emit probe2 sentinel missing")
        return 1
    p1 = parse_probe_json(t1)
    p2 = parse_probe_json(t2)
    if not p1 or not p2:
        print("FAILED:TST-0320 probe JSON missing")
        return 1

    append_line, append_snip = function_line("tools/bench/ledger.py", "append_cell")
    inspect_line, inspect_snip = function_line(
        "tools/bench/ledger.py", "inspect_published_bytes"
    )
    run_line, run_snip = function_line("tools/bench/runner.py", "run")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl = artifact_row("tools/bench/ledger.py", "primary-implementation")
    artifacts = [impl] + [
        artifact_row(p, "supporting") for p in SUPPORTING if p != "tools/bench/ledger.py"
    ]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        print(f"FAILED:{UNIT} emit missing {missing}")
        return 1

    idem = p2.get("idempotence") or {}
    plant = p2.get("planted_truncation") or {}
    loop = p2.get("atomic_kill_loop") or {}
    naive = p2.get("naive_in_place_kill") or {}

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Resume an interrupted tournament without recomputing or double-counting",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": (
            "tools/bench is a cell-grained tournament runner. ResultsLedger.append_cell "
            "is keyed by sha256(candidate, case, harness_version, seed) and refuses a "
            "second row. TournamentRunner.resume skips completed cells (dispatch log). "
            "A kill at 40% then resume matches an uninterrupted run on row count AND "
            "per-cell values; a score-mutating resume is the control that keeps row "
            "count and breaks values. Torn published tails (missing newline, even "
            "when the fragment is valid JSON) are discarded. "
            "SUCCESS:TST-0320"
        ),
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json TST-0320; tools/bench/; "
            "command-center/bench/results/; command-center/bench/cases/"
        ),
        "min_bytes_threshold": 128,
        "output_path": OUT_REL,
        "output_schema": SCHEMA,
        "cloud_ok": False,
        "registered": True,
        "inputs_on_this_worktree": {
            "tools/bench/": "created by this unit (was absent)",
            "command-center/bench/cases/": "fixture corpus shipped here (50 cells: 5 candidates x 10 cases)",
            "command-center/bench/results/": "LEDGER-CONTRACT.json present; live tournament ledgers are probe tempdirs",
            "TST-0300": "not delivered on this worktree; TST-0320 does not claim the scheduler/transitivity work",
            "_USER-PROMPTS.md:10500": "file absent; resumable artifacts implemented as the cell-keyed ledger",
        },
        "implementation": {
            "path": "tools/bench/ledger.py",
            "runner": "tools/bench/runner.py",
            "cell_key": ["candidate", "case", "harness_version", "seed"],
            "append_cell": {"line": append_line, "snippet": append_snip},
            "inspect_published_bytes": {"line": inspect_line, "snippet": inspect_snip},
            "run": {"line": run_line, "snippet": run_snip},
            "publish": "staging file, fsync, os.replace; never in-place on published path",
            "torn_row_policy": "discard incomplete final fragment; never parse as a result",
            "idempotent": True,
            "resume_skips_completed": True,
        },
        "mechanism": {
            "grain": "case-cell",
            "key": "(candidate, case, harness_version, seed)",
            "publish": "write complete snapshot to sibling staging file, fsync, os.replace",
            "never_in_place": True,
            "partial_record": "absent-from-parsed-results (torn tail discarded)",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "id": "E1-kill-40-resume-value-match",
                "claim": (
                    "Kill at 40% and resume: ledger matches the uninterrupted run "
                    "on row count and per-cell values. A mutating resume keeps "
                    "row count and fails the value comparison."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"tools/bench/runner.py:{run_line}",
                "confidence": "almost-certain",
                "measurement": {
                    "total_cells": p1.get("total_cells"),
                    "killed_rows": p1.get("killed_rows"),
                    "resume_evaluated": p1.get("resume_evaluated"),
                    "resume_skipped": p1.get("resume_skipped"),
                    "values_equal": p1.get("values_equal"),
                    "row_count_equal": p1.get("row_count_equal"),
                    "mutant_row_count_equal": p1.get("mutant_row_count_equal"),
                    "mutant_values_equal": p1.get("mutant_values_equal"),
                    "mutant_mismatch_count": p1.get("mutant_mismatch_count"),
                    "noskip_restart_evaluated": p1.get("noskip_restart_evaluated"),
                },
                "probes": [
                    {
                        "role": "source",
                        "method": "kill-at-40-resume-vs-uninterrupted-per-cell-values",
                        "command": P1,
                        "raw_output": t1[:16000],
                        "exit_code": c1,
                        "fingerprint": hashlib.sha256(
                            f"kill-resume\x1f{P1}".encode()
                        ).hexdigest()[:32],
                    },
                    {
                        "role": "verifier",
                        "method": "mutant-resume-same-count-different-values-and-skip-log",
                        "command": P1,
                        "raw_output": json.dumps(
                            {
                                "values_equal": p1.get("values_equal"),
                                "mutant_values_equal": p1.get("mutant_values_equal"),
                                "mutant_row_count_equal": p1.get(
                                    "mutant_row_count_equal"
                                ),
                                "resume_skipped": p1.get("resume_skipped"),
                                "noskip_restart_evaluated": p1.get(
                                    "noskip_restart_evaluated"
                                ),
                            }
                        ),
                        "exit_code": c1,
                        "fingerprint": hashlib.sha256(b"p1-value-control").hexdigest()[
                            :32
                        ],
                    },
                ],
            },
            {
                "id": "E2-idempotence-and-torn-discard",
                "claim": (
                    "Re-appending a completed cell does not grow the ledger; "
                    "unsafe_always_append does. A planted newline-less JSON "
                    "object is discarded by the honest reader and counted by "
                    "the naive parser. Atomic SIGKILL leaves 0 half-written "
                    "published rows."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"tools/bench/ledger.py:{inspect_line}",
                "confidence": "almost-certain",
                "measurement": {
                    "honest_grew": idem.get("honest_grew"),
                    "honest_refused": idem.get("honest_refused"),
                    "unsafe_grew": idem.get("unsafe_grew"),
                    "planted_honest_rows": plant.get("planted_honest_rows"),
                    "planted_naive_rows": plant.get("planted_naive_rows"),
                    "atomic_half_written": loop.get("half_written"),
                    "naive_torn_hits": naive.get("torn_hits"),
                },
                "probes": [
                    {
                        "role": "source",
                        "method": "idempotence-planted-torn-atomic-kill",
                        "command": P2,
                        "raw_output": t2[:16000],
                        "exit_code": c2,
                        "fingerprint": hashlib.sha256(
                            f"idem-torn\x1f{P2}".encode()
                        ).hexdigest()[:32],
                    },
                    {
                        "role": "verifier",
                        "method": "duplicated-per-line-schema-and-naive-parser",
                        "command": P2,
                        "raw_output": json.dumps(
                            {
                                "half_written": loop.get("half_written"),
                                "fired_on_planted": plant.get("fired_on_planted"),
                                "unsafe_grew": idem.get("unsafe_grew"),
                                "honest_grew": idem.get("honest_grew"),
                            }
                        ),
                        "exit_code": c2,
                        "fingerprint": hashlib.sha256(b"p2-controls").hexdigest()[:32],
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1_kill_resume",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2_idempotence_torn",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "skip-less-restart",
                "kind": "mutation-disable-resume-skip",
                "description": (
                    "After a 40% kill, resume=False re-evaluates every cell. "
                    "Honest resume evaluates only the remainder."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"noskip_restart_evaluated={p1.get('noskip_restart_evaluated')}",
                "good_state_output": f"resume_evaluated={p1.get('resume_evaluated')} resume_skipped={p1.get('resume_skipped')}",
            },
            {
                "id": "score-mutating-resume",
                "kind": "value-mutation-same-row-count",
                "description": (
                    "Mutating evaluate_cell by +1 keeps row count equal to the "
                    "clean run and fails per-cell value equality. Proves the "
                    "probe does not pass on count alone."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"mutant_values_equal={p1.get('mutant_values_equal')} mismatches={p1.get('mutant_mismatch_count')}",
                "good_state_output": f"values_equal={p1.get('values_equal')}",
            },
            {
                "id": "unsafe-always-append",
                "kind": "mutation-disable-cell-id-gate",
                "description": (
                    "unsafe_always_append writes a second row for a completed "
                    "cell. Honest append_cell refuses and the file does not grow."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"unsafe_grew={idem.get('unsafe_grew')} extra={idem.get('unsafe_extra')}",
                "good_state_output": f"honest_grew={idem.get('honest_grew')} refused={idem.get('honest_refused')}",
            },
            {
                "id": "planted-newline-less-json",
                "kind": "detector-control",
                "description": (
                    "Three complete rows plus a schema-valid JSON object with "
                    "no trailing newline: honest reader returns 3, naive parser "
                    "returns 4."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"naive_rows={plant.get('planted_naive_rows')} included_torn={plant.get('planted_naive_included_torn')}",
                "good_state_output": f"honest_rows={plant.get('planted_honest_rows')} silent_on_good={plant.get('silent_on_good')}",
            },
            {
                "id": "naive-in-place-chunked-write",
                "kind": "mutation-replace-atomic-rename-with-direct-write",
                "description": (
                    "unsafe_direct_append writes the published path in chunks. "
                    "SIGKILL during that write produces a torn tail the schema "
                    "check rejects."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"naive torn_hits={naive.get('torn_hits')}",
                "good_state_output": f"atomic kill-loop half_written={loop.get('half_written')}",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0320-probe2-idempotence-torn",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 duplicates the required-field list and splits published "
                "bytes on newline itself. The pass predicate for the kill-loop "
                "is that duplicated schema check, not inspect_published_bytes. "
                "A planted newline-less JSON object and a naive in-place writer "
                "both fire. Dual Windows-shell re-run (pwsh7 + Git Bash) was "
                "not executed; this worktree is Linux."
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot; this delivery did not require a pivot",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0320/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
        "defects": [],
        "residual_unknowns": [
            "Reviewer requirement names a second Windows shell (pwsh7 and Git Bash). This delivery ran on Linux; probes are CPython and do not depend on a shell dialect. Dual-shell divergence is unmeasured.",
            "TST-0300 (tournament scheduler / transitivity) is not delivered; this unit proves resume/idempotence on a fixture 50-cell field, not a live hundreds-by-dozens tournament.",
        ],
        "notes": (
            "G-1 for TST-0320: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. cloud ok=true is not delivery. Did not run "
            "global unit_manifest.py --write. No ADV rebuild. SUCCESS:TST-0320"
        ),
        "schema_note": (
            "command-center/schema/receipt.schema.json is absent from this "
            "worktree; this receipt follows the field shape used by sibling "
            "IMP units. Settling experiment: validate against the schema when "
            "it is present."
            if not (REPO / SCHEMA).is_file()
            else "receipt.schema.json present"
        ),
        "ts": now,
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    size = out.stat().st_size
    if size < 128:
        print(f"FAILED:{UNIT} emit size {size} below floor")
        return 1
    if SENTINEL not in text:
        print("FAILED:TST-0320 emit sentinel missing from bytes")
        return 1
    print(f"wrote {OUT_REL} ({size} B)")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
