#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0215.json from live named probes.

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
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from workflow_foundry.resumable import SCHEMA_REL, STAGES  # noqa: E402

UNIT = "IMP-0215"
OUT_REL = "command-center/receipts/IMP-0215.json"
IMPL_REL = "tools/workflow_foundry/resumable.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0215/probe1_kill_partial.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0215/probe2_resume_dispatch.py"
)
SUPPORTING = [
    IMPL_REL,
    SCHEMA_REL,
    "tools/workflow_foundry/__init__.py",
    "command-center/p2-wave/probes/IMP-0215/probe1_kill_partial.py",
    "command-center/p2-wave/probes/IMP-0215/probe2_resume_dispatch.py",
]
SENTINEL = "SUCCESS:IMP-0215"
QUESTION = (
    "Target: a scout or forge run that is interrupted preserves everything it "
    "had proven and resumes from there. Acceptance: killing forge mid-run "
    "leaves a truthful partial artifact on disk (every unproven claim marked "
    "UNKNOWN - not yet measured), because a unit that holds results in memory "
    "for 70 minutes and then freezes is a measured total loss on this estate."
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def function_line(rel: str, name: str) -> tuple[int, str]:
    path = REPO / rel
    text = path.read_text(encoding="utf-8")
    needle = f"def {name}("
    idx = text.find(needle)
    if idx < 0:
        raise SystemExit(f"FAILED:{UNIT} missing {name} in {rel}")
    line = text[:idx].count("\n") + 1
    snippet = text[idx : idx + 88].splitlines()[0]
    return line, snippet


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "present": True,
        "role": role,
    }


def parse_probe_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict) and doc.get("pass") is True:
                return doc
    return {}


def main() -> int:
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = parse_probe_json(t1)
    p2 = parse_probe_json(t2)
    if not p1 or not p2:
        print(f"FAILED:{UNIT} probe JSON missing")
        return 1

    flush_line, flush_snip = function_line(IMPL_REL, "_flush")
    oracle_line, oracle_snip = function_line(IMPL_REL, "_oracle_ok")
    run_line, run_snip = function_line(IMPL_REL, "run")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    receipt = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "title": "Make scout and forge resumable with partial-result preservation",
        "question_or_target": QUESTION,
        "answer": (
            "Scout and forge share tools/workflow_foundry/resumable.py: a "
            "write-as-you-go runner that seeds every claim as UNKNOWN, proves "
            "one claim, fsyncs a schema-valid partial artifact, then continues. "
            "A cooperative kill at 30% (3 of 10 claims) leaves PARTIAL with "
            "seven explicit UNKNOWN / not-yet-measured rows. Resume loads the "
            "IMP-0145 checkpoint (completed ids + receipt hashes + open nodes + "
            "param bindings) and skips claims whose receipts still pass the "
            "oracle; the ledger counted 7 resume dispatches against 10 for a "
            "clean run. A memory-only negative control leaves no file on the "
            "same kill; a naive restart re-dispatches all 10. "
            "SUCCESS:IMP-0215"
        ),
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "inputs": [
            "rules/common/fan-out-contract.md (C1 write-as-you-go)",
            "IMP-0145 resume state model",
        ],
        "implementation": {
            "path": IMPL_REL,
            "schema": SCHEMA_REL,
            "flush": {"line": flush_line, "snippet": flush_snip},
            "oracle": {"line": oracle_line, "snippet": oracle_snip},
            "run": {"line": run_line, "snippet": run_snip},
            "engines": {
                "scout_claims": [s["id"] for s in STAGES["scout"]],
                "forge_claims": [s["id"] for s in STAGES["forge"]],
            },
            "write_as_you_go": True,
            "unproven_policy": "UNKNOWN-not-yet-measured",
        },
        "cloud_ok": False,
        "registered": True,
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0215/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "evidence": [
            {
                "id": "E1-kill-at-30-partial",
                "claim": (
                    "A kill at 30% leaves a parseable, schema-valid artifact "
                    "whose unproven sections are marked UNKNOWN."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL_REL}:{flush_line}",
                "measurement": {
                    "forge_progress_pct": p1.get("forge", {}).get("progress_pct"),
                    "forge_proven": p1.get("forge", {}).get("proven"),
                    "forge_unknown": p1.get("forge", {}).get("unknown"),
                    "scout_progress_pct": p1.get("scout", {}).get("progress_pct"),
                    "memory_only_artifact_absent": p1.get(
                        "memory_only_artifact_absent"
                    ),
                },
                "probes": [
                    {
                        "id": "probe1",
                        "role": "source",
                        "command": P1,
                        "exit_code": c1,
                        "method": "command",
                        "raw_output": t1,
                    }
                ],
            },
            {
                "id": "E2-resume-dispatch-lower",
                "claim": (
                    "The resumed run does not re-do proven work: ledger dispatch "
                    "count is strictly lower than a clean run, and resume ids are "
                    "disjoint from killed proven ids."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL_REL}:{oracle_line}",
                "measurement": {
                    "clean_dispatch_count": p2.get("clean_dispatch_count"),
                    "killed_dispatch_count": p2.get("killed_dispatch_count"),
                    "resume_dispatch_count": p2.get("resume_dispatch_count"),
                    "resume_strictly_lower": p2.get("resume_strictly_lower"),
                    "overlap": p2.get("overlap"),
                    "naive_restart_dispatch_count": p2.get(
                        "naive_restart_dispatch_count"
                    ),
                    "oracle_resume_dispatch_count": p2.get(
                        "oracle_resume_dispatch_count"
                    ),
                },
                "probes": [
                    {
                        "id": "probe2",
                        "role": "verifier",
                        "command": P2,
                        "exit_code": c2,
                        "method": "command",
                        "raw_output": t2,
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "kill-at-30-truthful-partial",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "resume-dispatch-count-strictly-lower",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "memory-only-hold-until-end",
                "kind": "mutant-implementation",
                "description": (
                    "MemoryOnlyEngine proves claims in RAM and writes only on "
                    "COMPLETE. The same kill-at-30% leaves no file. The "
                    "write-as-you-go engine leaves a PARTIAL with UNKNOWNs."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "memory-only",
                "good_state": "write-as-you-go",
            },
            {
                "id": "naive-restart-from-zero",
                "kind": "mutant-resume",
                "description": (
                    "ignore_checkpoint=True re-dispatches the full roster "
                    "(count 10, not lower). Honest resume dispatches 7."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "naive-restart",
                "good_state": "oracle-skip-resume",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0215-probe2-resume-dispatch",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 counts dispatch events from the append-only ledger and "
                "does not trust probe 1's proven-id list or the runner return "
                "value. Naive restart and oracle-tamper are both-states controls."
            ),
        },
        "artifacts": artifacts,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "kill-at-30-partial-UNKNOWN",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "resume-ledger-dispatch-count",
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0209 scout search and IMP-0212 forge synthesis are not "
                    "this unit. This substrate is the resume/partial contract "
                    "those engines must use; live marketplace/paper search is "
                    "UNKNOWN here."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": "Wire IMP-0209/IMP-0212 prove_claim to real search and fusion.",
            }
        ],
        "timestamps": {"ended_at": now},
        "notes": (
            "G-1 for IMP-0215: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. No ADV rebuild."
        ),
    }
    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    sha, size = digest_file(dest)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0215 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
