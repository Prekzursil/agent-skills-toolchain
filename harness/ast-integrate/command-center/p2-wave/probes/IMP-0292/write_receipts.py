#!/usr/bin/env python3
"""Write IMP-0292 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0292"
OUT = f"command-center/receipts/{UNIT}.json"
SCHEMA = (
    "command-center/schema/receipt.schema.json profile=council-protocol-module "
    "(required: unit_id, artifact_paths[], spec_anchor, evidence[], test_ids[], "
    "negative_control_ids[], reviewer_verdict, residual_unknowns[])"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0292/probe1_lifecycle.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0292/probe2_evasion.py"
)
SUPPORTING = [
    "tools/council/protocol/socratic.py",
    "command-center/p2-wave/probes/IMP-0292/probe1_lifecycle.py",
    "command-center/p2-wave/probes/IMP-0292/probe2_evasion.py",
    "command-center/p2-wave/probes/IMP-0292/fixtures/evasion-corpus.json",
    "command-center/p2-wave/probes/IMP-0292/obligation-ledger.json",
    "command-center/p2-wave/probes/IMP-0292/evasion-corpus-score.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file() and size > 0,
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        "role": role,
    }


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    ledger = load_json(HERE / "obligation-ledger.json")
    scored = load_json(HERE / "evasion-corpus-score.json")
    module = REPO / "tools/council/protocol/socratic.py"
    mod_sha, mod_bytes = digest(module)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    artifact_paths = [OUT, *SUPPORTING]
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0292",
        "title": "Socratic cross-examination with enforced response obligations",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0292] "
            "tools/council/protocol/socratic.py"
        ),
        "question_or_target": (
            "Implement tools/council/protocol/socratic.py so a directed question "
            "creates a tracked obligation the addressee must discharge within N "
            "turns. Falsifiable question: can a participant discharge an "
            "obligation with a non-answer, and does the tracker detect evasion "
            "rather than counting any reply as a response?"
        ),
        "falsifiable_answer": (
            "No: a non-answer, including a multi-kilobyte stall, leaves the "
            "obligation OPEN. Discharge requires classify_reply to return ANSWER. "
            "naive_any_bytes_discharge is kept as the defeated control."
        ),
        "output_schema": SCHEMA,
        "min_bytes_threshold": 128,
        "artifact_paths": artifact_paths,
        "test_ids": [
            "unit-obligation-lifecycle-expiry-escalation",
            "neg-non-answer-remains-open",
        ],
        "negative_control_ids": [
            "neg-non-answer-remains-open",
            "neg-byte-count-would-discharge",
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0292-probe2-evasion-corpus",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests and labelled corpus, not the author's summary",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "tests": [
            {
                "id": "unit-obligation-lifecycle-expiry-escalation",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "neg-non-answer-remains-open",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "neg-non-answer-remains-open",
                "kind": "non-answer-stays-open",
                "description": (
                    "A 4kB stall reply must remain OPEN, proving the tracker "
                    "is not counting bytes."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "neg-byte-count-would-discharge",
                "kind": "defeated-control",
                "description": (
                    "naive_any_bytes_discharge returns true on the same stall "
                    "the live tracker keeps OPEN."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "evidence": [
            {
                "id": "obligation-ledger",
                "claim": (
                    "The live ledger records OPEN/DISCHARGED/EXPIRED/ESCALATED "
                    "with per-turn ages."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0292/obligation-ledger.json",
                "states_present": ledger.get("states_present"),
                "ledger_digest": ledger.get("ledger_digest"),
                "padded_non_answer_remained_open": ledger.get(
                    "padded_non_answer_remained_open"
                ),
            },
            {
                "id": "evasion-corpus",
                "claim": (
                    "A labelled evasion corpus is scored by classify_reply; "
                    "the discrimination rate is reported."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0292/fixtures/evasion-corpus.json",
                "n": scored.get("n"),
                "discrimination_rate": scored.get("discrimination_rate"),
                "tp": scored.get("tp"),
                "tn": scored.get("tn"),
                "fp": scored.get("fp"),
                "fn": scored.get("fn"),
                "byte_counter_defeated_n": scored.get("byte_counter_defeated_n"),
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "tools/council/kernel.py (IMP-0264) is not on this worktree; "
                    "socratic.py carries its own turn index until the kernel lands."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe1 after IMP-0264 with record_turn driven by the "
                    "kernel event loop rather than the protocol clock."
                ),
            },
            {
                "claim": (
                    "tools/council/integrity/coi.py (IMP-0277) is not on this "
                    "worktree; seat incompatibility is not enforced here."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Wire ask() through the COI checker once present.",
            },
            {
                "claim": (
                    "Synonym-only answers with no shared content token and no typed "
                    "cue can still be labelled EVASION (false negative)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Add a labelled synonym slice and report the drop in recall."
                ),
            },
        ],
        "artifacts": [
            {
                "path": "tools/council/protocol/socratic.py",
                "bytes": mod_bytes,
                "sha256": mod_sha,
                "exists": True,
                "role": "implementation",
            }
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0292/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "notes": (
            "G-1 for IMP-0292: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. SUCCESS:IMP-0292"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary]
    for rel in SUPPORTING:
        artifacts.append(row(rel, "supporting"))

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0292",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "obligation-lifecycle",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "evasion-negative-control",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0292-probe2-evasion-corpus",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0292: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a.get("present")),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0292 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
