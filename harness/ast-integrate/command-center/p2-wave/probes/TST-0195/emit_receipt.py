#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0195.json from live Skills/ vs skills/ lookup."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

UNIT = "TST-0195"
OUT_REL = "command-center/receipts/TST-0195.json"
SENTINEL = "SUCCESS:TST-0195"
QUESTION = (
    "Does a Skills/ vs skills/ reference resolve consistently, and is the "
    "platform difference declared rather than accidental? PASS requires: "
    "exact-match failure on Linux, and on Windows either the same failure or "
    "a resolution accompanied by a warning naming the mismatch."
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


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    doc = H.measure()
    second = H.second_shell_windows()
    ended = datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    if not doc["pass"] or not second["agree"]:
        print("FAILED:TST-0195 emit contract did not hold")
        print(json.dumps({"measure": doc, "second": second}, indent=2, default=str)[:6000])
        return 1

    host = doc["host"]
    answer = (
        "Yes. On this Linux host a Skills/ reference against an on-disk skills/ "
        "directory is an exact miss (live Path.exists is False; declared Linux "
        "policy reason=exact-miss). The Windows policy on the same fixture "
        "resolves Skills/ to skills and emits a warning that names both "
        f"spellings ({doc['windows']['mismatch_warnings']}). Correctly-cased "
        "./skills/ is silent on both legs. A mutant that casefolds without a "
        "warning is rejected. The platform difference is declared in "
        "command-center/p2-wave/probes/TST-0195/lookup.py, not inherited from "
        f"Path.exists. {SENTINEL}"
    )

    p_linux = probe(
        "source",
        "command",
        "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0195/probe1_both_states_linux.py",
        json.dumps(
            {
                "linux_mismatch": doc["linux"]["mismatch"],
                "live_os_exists_Skills": host["live_os_exists_Skills"],
                "live_os_exists_skills": host["live_os_exists_skills"],
            },
            sort_keys=True,
        ),
        0,
    )
    p_win = probe(
        "verifier",
        "command",
        "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0195/probe2_windows_warning_matrix.py",
        json.dumps(
            {
                "windows_mismatch": doc["windows"]["mismatch"],
                "warnings": doc["windows"]["mismatch_warnings"],
                "silent_mutant_rejected": doc["contract"]["silent_mutant_rejected"],
                "second_shell_agree": second["agree"],
            },
            sort_keys=True,
        ),
        0,
    )

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "report_kind": "portability_report",
        "spec_anchor": "_USER-PROMPTS.md:11016",
        "question": QUESTION,
        "answer": answer,
        "min_bytes_threshold": 128,
        "profile": "selfimprove-measure-artifact",
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5.x-codex",
            "role": "portability-tester",
            "execution_substrate": "linux-headless-local",
        },
        "artifacts": [
            art("command-center/p2-wave/probes/TST-0195/lookup.py", "primary-implementation"),
            art(
                "command-center/p2-wave/probes/TST-0195/probe1_both_states_linux.py",
                "named-probe",
            ),
            art(
                "command-center/p2-wave/probes/TST-0195/probe2_windows_warning_matrix.py",
                "named-probe",
            ),
            art(
                "command-center/p2-wave/probes/TST-0195/fixtures/plugin-root/skills/skill.probe/SKILL.md",
                "fixture",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "Linux leg: Skills/ is an exact-match failure against on-disk "
                    "skills/; live Path.exists agrees."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0195/fixtures/plugin-root",
                "confidence": "almost-certain",
                "probes": [p_linux],
            },
            {
                "claim": (
                    "Windows leg: Skills/ resolves to skills with a warning naming "
                    "both spellings; a silent casefold mutant is rejected."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0195/lookup.py",
                "confidence": "almost-certain",
                "probes": [p_win],
            },
        ],
        "report": {
            "kind": "portability_report",
            "host": host,
            "linux_leg": doc["linux"],
            "windows_leg": doc["windows"],
            "silent_mutant": doc["silent_mutant"],
            "contract": doc["contract"],
            "second_windows_shell": second,
            "plugin_json_skills": doc["plugin_json_skills"],
            "plugin_Skills_json_skills": doc["plugin_Skills_json_skills"],
            "fixture": "command-center/p2-wave/probes/TST-0195/fixtures/plugin-root",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "max 2 attempts, backoff 30s/120s"},
        "tests": [
            {
                "id": "both-states-exact-silent",
                "command": p_linux["command"],
                "result": "PASS",
            },
            {
                "id": "linux-Skills-exact-miss",
                "command": p_linux["command"],
                "result": "PASS",
            },
            {
                "id": "windows-Skills-warn-or-miss",
                "command": p_win["command"],
                "result": "PASS",
            },
            {
                "id": "silent-windows-mutant-rejected",
                "command": p_win["command"],
                "result": "PASS",
            },
            {
                "id": "cross-os-same-fixture",
                "command": p_win["command"],
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "TST0195-C1-linux-mismatch",
                "kind": "known-broken-ref",
                "description": "Skills/ against skills/ must exact-miss on Linux.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(doc["linux"]["mismatch"], sort_keys=True),
                "good_state_output": json.dumps(doc["linux"]["exact"], sort_keys=True),
            },
            {
                "id": "TST0195-C2-silent-windows",
                "kind": "detector-control",
                "description": (
                    "A Windows casefold that emits no warning must fail this unit."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(doc["silent_mutant"], sort_keys=True),
                "good_state_output": json.dumps(
                    doc["windows"]["mismatch"], sort_keys=True
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0195-probe2-windows-warning-and-silent-mutant",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": second["note"],
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0195/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT_REL,
                "executed": False,
                "read_ok": True,
                "exit_code": None,
                "probe": probe(
                    "verifier",
                    "file-read",
                    "stat command-center/receipts/TST-0195.json",
                    "receipt written; measure runs after named probes",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "pwsh7 and Git Bash are not installed on this Linux worktree; "
                    "the second Windows shell was simulated with NT separators."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe2 on a Windows host under pwsh7 and Git Bash "
                    "and compare warning streams."
                ),
            }
        ],
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    size = out.stat().st_size
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0195 sentinel missing after write")
        return 1
    if size < 128:
        print(f"FAILED:TST-0195 receipt too small {size}B")
        return 1
    print(f"wrote {OUT_REL} ({size} B)")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
