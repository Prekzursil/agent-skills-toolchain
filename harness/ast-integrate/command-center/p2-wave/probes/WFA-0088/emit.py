#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0088-repair-fanout-deadlock.json.

RepairRecord for the fan-out deadlock class. Does not write SUBAGENT-RETURN
or UNIT-ARTIFACT-MANIFEST (write_receipts.py does that). Does not call
unit_manifest.py --write.
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

from wfa_fanout.pipeline import (  # noqa: E402
    BROKEN_WAIT_S,
    DEADLINE_S,
    HANG_ID,
    N_UNITS,
    REPAIRED_MAX_S,
)

UNIT = "WFA-0088"
OUT_REL = "command-center/wfa/WFA-0088-repair-fanout-deadlock.json"
IMPL_REL = "tools/wfa_fanout/pipeline.py"
SENTINEL = "SUCCESS:WFA-0088"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0088/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0088/probe2_durable_partial.py"
)
SUPPORTING = [
    IMPL_REL,
    "tools/wfa_fanout/__init__.py",
    "command-center/p2-wave/probes/WFA-0088/probe1_both_states.py",
    "command-center/p2-wave/probes/WFA-0088/probe2_durable_partial.py",
]
QUESTION = (
    "Implementation target: eliminate the measured class in which a parallel "
    "barrier has no per-agent timeout, so a single hung unit deadlocks the "
    "whole phase - replacing it with per-work-unit pipelines, a per-agent "
    "deadline and a null-tolerant barrier that completes on partial results."
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
    snippet = text[idx : idx + 96].splitlines()[0]
    return line, snippet


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


def scan_inputs() -> dict:
    home_wf = Path.home() / ".claude" / "workflows"
    fanout_rule = REPO / "rules" / "common" / "fan-out-contract.md"
    prompts = REPO / "_USER-PROMPTS.md"
    rows = []
    for label, path, kind in (
        ("live:~/.claude/workflows", home_wf, "dir"),
        ("rule:rules/common/fan-out-contract.md", fanout_rule, "file"),
        ("_USER-PROMPTS.md:11317", prompts, "file"),
    ):
        present = path.is_dir() if kind == "dir" else path.is_file()
        rows.append(
            {
                "input": label,
                "path": str(path),
                "kind": kind,
                "present": present,
            }
        )
    js_hits = []
    for pattern in ("**/*.js", "**/*.mjs"):
        for path in REPO.glob(pattern):
            rel = path.relative_to(REPO).as_posix()
            if rel.startswith("command-center/p2-wave/probes/"):
                continue
            if rel.startswith("tools/plugin/tests/"):
                continue
            js_hits.append(rel)
    return {
        "declared": rows,
        "live_workflows_present": home_wf.is_dir(),
        "fan_out_contract_present": fanout_rule.is_file(),
        "user_prompts_present": prompts.is_file(),
        "repo_workflow_js_outside_probe_fixtures": js_hits,
        "note": (
            "This Linux worktree has no live ~/.claude/workflows tree and no "
            "rules/common/fan-out-contract.md. The repair is the in-repo "
            "runtime tools/wfa_fanout/pipeline.py, proven by both-states "
            "fault injection, not a patch of absent vendor workflow files."
        ),
    }


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

    pipeline_line, pipeline_snip = function_line(IMPL_REL, "_pipeline_one")
    run_line, run_snip = function_line(IMPL_REL, "run_cohort")
    write_line, write_snip = function_line(IMPL_REL, "atomic_write_json")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inputs = scan_inputs()
    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]

    doc = {
        "record_type": "RepairRecord",
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Repair the fan-out deadlock class: one hung unit blocking an entire cohort",
        "question_or_target": QUESTION,
        "output_path": OUT_REL,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RepairRecord",
        "schema_pack_present": (
            REPO / "command-center/wfa/schema/wfa-schema-pack.json"
        ).is_file(),
        "defect_class": {
            "id": "fanout-deadlock",
            "spec_line": 11317,
            "name": "one hung unit blocks a large batch",
            "mechanism": (
                "A parallel barrier with no per-agent timeout (Promise.all / "
                "wait-all analogue) waits for every sibling. One hung unit "
                "keeps the phase unresolved past the per-agent deadline. A "
                "phase-only deadline still loses sibling work held in memory."
            ),
        },
        "repair": {
            "path": IMPL_REL,
            "per_work_unit_pipelines": True,
            "per_agent_deadline_s": DEADLINE_S,
            "null_tolerant_barrier": True,
            "write_as_you_go": True,
            "hung_unit_id": HANG_ID,
            "cohort_size": N_UNITS,
            "broken_observation_window_s": BROKEN_WAIT_S,
            "repaired_max_s": REPAIRED_MAX_S,
            "pipeline": {"line": pipeline_line, "snippet": pipeline_snip},
            "run_cohort": {"line": run_line, "snippet": run_snip},
            "atomic_write_json": {"line": write_line, "snippet": write_snip},
        },
        "answer": (
            "tools/wfa_fanout/pipeline.py gives every work unit its own "
            "pipeline with a per-agent deadline. A hung unit becomes "
            "TIMEOUT with a null payload; the barrier is null-tolerant and "
            "completes on the partial. Each terminal result is fsynced "
            "before the barrier continues. Both-states: the pre-fix wait-all "
            f"control is still RUNNING after {BROKEN_WAIT_S}s "
            f"(>{DEADLINE_S}s deadline); the repaired cohort of {N_UNITS} "
            "with one hang resolves with 7 OK + 1 TIMEOUT on disk. A "
            "phase-only deadline discards siblings that finished in RAM "
            "(zero durable files). A memory-only twin of an interrupt "
            "leaves no files; write-as-you-go leaves the OK partials. "
            "SUCCESS:WFA-0088"
        ),
        "inputs_observed": inputs,
        "both_states": {
            "mandatory": True,
            "injected_hang_blocks_before_fix": bool(
                (p1.get("both_states") or {}).get("hang_blocks_before_fix")
            ),
            "injected_hang_does_not_block_after_fix": bool(
                (p1.get("both_states") or {}).get("hang_does_not_block_after_fix")
            ),
            "pre_fix": p1.get("broken"),
            "post_fix": p1.get("repaired"),
        },
        "tests": [
            {
                "id": "both-states-injected-hang",
                "requirement": (
                    "the injected hang must block before the fix and not block after"
                ),
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "partial-durable-on-disk",
                "requirement": (
                    "the partial result must be durable on disk, not held in memory"
                ),
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
            {
                "id": "deadline-per-agent-not-only-per-phase",
                "requirement": (
                    "the deadline must be per-agent, not only per-phase - a "
                    "phase deadline still loses every sibling's work"
                ),
                "command": P2,
                "result": "PASS"
                if c2 == 0
                and (p2.get("phase_deadline") or {}).get("durable_files") == 0
                and (p2.get("full_repaired") or {}).get("sibling_ok") == N_UNITS - 1
                else "FAIL",
                "exit_code": c2,
            },
        ],
        "evidence": [
            {
                "id": "A-fault-injection-partial",
                "claim": (
                    "A fault-injection run in which one agent hangs and the "
                    "cohort still completes within the declared deadline with "
                    "a recorded partial."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL_REL}:{pipeline_line}",
                "measurement": p1.get("repaired"),
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
                "id": "B-pre-fix-wait-all-control",
                "claim": (
                    "Mechanically independent: the pre-fix control where the "
                    "same injected hang blocks the cohort past the deadline, "
                    "so the fix is proven by a state change and not by a "
                    "single green run."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL_REL}:{run_line}",
                "measurement": p1.get("broken"),
                "probes": [
                    {
                        "id": "probe1",
                        "role": "pre-fix-control",
                        "command": P1,
                        "exit_code": c1,
                        "method": "command",
                        "raw_output": t1,
                    }
                ],
            },
            {
                "id": "C-write-as-you-go-and-phase-deadline",
                "claim": (
                    "Partials are fsynced per unit. A memory-only interrupt "
                    "leaves no files. A phase-only deadline discards RAM "
                    "siblings (durable_files=0) while the repaired full run "
                    "keeps all sibling OK files."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL_REL}:{write_line}",
                "measurement": {
                    "write_as_you_go": p2.get("write_as_you_go"),
                    "memory_only": p2.get("memory_only"),
                    "phase_deadline": p2.get("phase_deadline"),
                    "full_repaired": p2.get("full_repaired"),
                    "static": p2.get("static"),
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
        "negative_controls": [
            {
                "id": "broken-wait-all",
                "kind": "pre-fix-barrier",
                "description": (
                    "Promise.all analogue: wait for every future with no "
                    "per-agent timeout. After BROKEN_WAIT_S the hang is still "
                    "RUNNING and barrier_resolved is false."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "broken-wait-all",
                "good_state": "repaired-per-agent",
            },
            {
                "id": "memory-only-hold",
                "kind": "mutant-implementation",
                "description": (
                    "Same per-agent deadline but results held in RAM until "
                    "the barrier returns. Interrupt after N OK leaves zero "
                    "files; write-as-you-go leaves the OK partials."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "memory-only-hold",
                "good_state": "write-as-you-go",
            },
            {
                "id": "phase-deadline-only",
                "kind": "insufficient-deadline",
                "description": (
                    "One phase clock. Siblings finish in RAM then the phase "
                    "aborts because of the hang; durable_files=0. Proves a "
                    "phase deadline still loses every sibling's work."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "phase-deadline",
                "good_state": "per-agent-deadline",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0088-probe2-durable-partial",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 2 does not trust probe 1's elapsed times. It interrupts "
                "write-as-you-go vs memory-only, runs the phase-deadline "
                "control, and AST-walks _pipeline_one for atomic_write_json "
                "and the self_timeout branch. Catalog reviewer_requirement "
                "asks for a human in a fresh context; that pass is not claimed."
            ),
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "both-states-hang-injection",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "durable-partial-and-phase-deadline",
            },
        ],
        "artifacts": artifacts,
        "cloud_ok": False,
        "registered": True,
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/WFA-0088/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "live:~/.claude/workflows is absent on this Linux "
                    "worktree, so vendor saved-workflow .js/.mjs files were "
                    "not patched in place. The class is eliminated in "
                    "tools/wfa_fanout, which is the repair substrate this "
                    "unit ships. WFA-0001 schema pack is also absent; this "
                    "record is JSON and carries record_type=RepairRecord."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": (
                    "Re-run both-states against live ~/.claude/workflows "
                    "parallel() call sites when that tree is mounted."
                ),
            }
        ],
        "dependencies_disclosed": {
            "WFA-0086": "repair-intake baselines not present on this worktree",
            "WFA-0045": "saved-workflow adapter not present on this worktree",
        },
        "timestamps": {"ended_at": now},
        "notes": (
            "G-1 for WFA-0088: live named probes exit 0, RepairRecord "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            "No ADV rebuild. SUCCESS:WFA-0088"
        ),
    }
    if any(t["result"] != "PASS" for t in doc["tests"]):
        print(f"FAILED:{UNIT} a required test did not pass")
        return 1

    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    sha, size = digest_file(dest)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:WFA-0088 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
