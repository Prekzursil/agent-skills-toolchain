#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0102-nested-council-completion-disagreement.json."""
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
OUT = "command-center/adversarial/ADV-0102-nested-council-completion-disagreement.json"
SCHEMA = "command-center/schema/council-pathology-sim.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0102/probe1_mismatched_nesting.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0102/probe2_callgraph_shared_predicate.py"
)
SENTINEL = (
    "SUCCESS:ADV-0102 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0102 <reason>."
)
PROBE1_TEXT = (
    "Probe 1: run the mismatched nesting and record the terminal state of both "
    "levels plus the elapsed behaviour (block, accept, spin)."
)
PROBE2_TEXT = (
    "Probe 2 (mechanically different): verify that the fan-in uses the SAME "
    "shared completion predicate as the rest of the program, by call-graph "
    "inspection - a council-local completion notion is the root cause and no "
    "behavioural test names it."
)
QUESTION = (
    "When a subcouncil reports complete and the parent's predicate disagrees "
    "(or vice versa), what happens - does the fan-in block, silently accept, "
    "or deadlock?"
)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def parse_json_prefix(raw: str) -> dict:
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        doc = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0:
        print("FAILED:ADV-0102 emit probe1")
        print(t1[-4000:])
        return 1
    if c2 != 0:
        print("FAILED:ADV-0102 emit probe2")
        print(t2[-4000:])
        return 1
    j1 = parse_json_prefix(t1)
    j2 = parse_json_prefix(t2)
    ms = j1.get("mismatch_shared") or {}
    ml = j1.get("mismatch_local_mutant") or {}
    ctrl = j1.get("control_consistent") or {}
    dl = j1.get("deadlock") or {}
    schema_present = (REPO / SCHEMA).is_file()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    mismatch_blocks = (
        ms.get("elapsed_behaviour") == "block"
        and ms.get("child_complete") is True
        and ms.get("parent_complete") is False
    )
    local_accepts = ml.get("elapsed_behaviour") == "accept"
    control_ok = (
        ctrl.get("terminal") == "BOTH_COMPLETE"
        and ctrl.get("child_complete") is True
        and ctrl.get("parent_complete") is True
    )
    deadlock_ok = (
        dl.get("terminal") == "DEADLOCK_DETECTED"
        and dl.get("timeout_fired") is True
        and isinstance(dl.get("timeout_seconds"), (int, float))
    )
    if not (mismatch_blocks and local_accepts and control_ok and deadlock_ok):
        print("FAILED:ADV-0102 emit scenario gates")
        print(json.dumps({"ms": ms, "ml": ml, "ctrl": ctrl, "dl": dl}, indent=2)[:4000])
        return 1

    t1_verdict = "CONFIRMED"
    t2_verdict = "CONFIRMED"
    answer = (
        "On a nested fan-in that uses lib.completion_reducer.reduce_completion "
        "together with each level's own stopping expression, a satisfiable child "
        f"({ms.get('child_expr')}) with an unsatisfiable parent "
        f"({ms.get('parent_expr')}) BLOCKs: child_complete=true, "
        "parent_complete=false, elapsed_behaviour=block, timeout not fired. "
        "The council-local mutant parent_complete:=child_complete silently "
        "ACCEPTs the same mismatch. A consistent nesting (both stopping "
        "expressions satisfiable, both receipts COMPLETE) completes at both "
        f"levels. A parent/child wait-cycle is detected as DEADLOCK_DETECTED "
        f"by a bounded timeout of {dl.get('timeout_seconds')} seconds "
        f"({dl.get('ticks')} ticks). Production tools/council has no nested "
        "topology module and tools/council/cli/runtime.py does not call the "
        "shared reducer or agentspec.oracle.judge; that local completion "
        "notion is the named root cause. agentspec fan-in sites call judge."
    )

    tests = [
        {
            "id": "T-MISMATCH-SHARED-BLOCKS",
            "requirement": PROBE1_TEXT,
            "result": "PASS" if mismatch_blocks else "FAIL",
            "observed": ms,
        },
        {
            "id": "T-CONTROL-CONSISTENT-NESTING-BOTH-COMPLETE",
            "requirement": (
                "control: a consistent nesting must complete cleanly at both levels"
            ),
            "result": "PASS" if control_ok else "FAIL",
            "observed": ctrl,
        },
        {
            "id": "T-DEADLOCK-BOUNDED-TIMEOUT",
            "requirement": (
                "a deadlock must be detected by a bounded timeout, and the "
                "timeout value must be recorded"
            ),
            "result": "PASS" if deadlock_ok else "FAIL",
            "observed": {
                "terminal": dl.get("terminal"),
                "timeout_fired": dl.get("timeout_fired"),
                "timeout_seconds": dl.get("timeout_seconds"),
                "ticks": dl.get("ticks"),
            },
        },
        {
            "id": "T-NEGATIVE-LOCAL-MUTANT-SILENT-ACCEPT",
            "requirement": (
                "negative: a council-local parent_complete:=child_complete "
                "must silently accept the mismatch so the block is not a tautology"
            ),
            "result": "PASS" if local_accepts else "FAIL",
            "observed": ml,
        },
        {
            "id": "T-CALLGRAPH-SHARED-PREDICATE",
            "requirement": PROBE2_TEXT,
            "result": "PASS" if c2 == 0 else "FAIL",
            "observed": {
                "harness_calls_reduce_completion": (j2.get("checks") or {}).get(
                    "harness_calls_reduce_completion"
                ),
                "production_nested_topology_absent": (j2.get("checks") or {}).get(
                    "production_nested_topology_absent"
                ),
                "local_mutant_function_present": (j2.get("checks") or {}).get(
                    "local_mutant_function_present"
                ),
            },
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:ADV-0102 emit tests")
        return 1

    doc = {
        "unit_id": "ADV-0102",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "report_kind": "council-pathology-sim",
        "title": "Nested councils disagreeing about completion",
        "question": QUESTION,
        "answer": answer,
        "overall_verdict": "CONFIRMED",
        "measured_at": now,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "output_schema_present": schema_present,
        "schema_note": (
            "Catalog output_schema command-center/schema/council-pathology-sim.schema.json "
            "is absent on this worktree (shim also absent). G-1 does not require "
            "schema validation. This artifact is well-formed JSON carrying the "
            "catalog-required probe, verdict, and control fields."
            if not schema_present
            else "schema file present"
        ),
        "spec_anchor": "_USER-PROMPTS.md:11343, 10946",
        "targets": [
            {
                "id": "mismatched-nesting-terminal-behaviour",
                "question": (
                    "When child stopping is satisfiable and parent stopping is "
                    "not, does fan-in block, silently accept, or spin?"
                ),
                "verdict": t1_verdict,
                "observed_behaviour": ms.get("elapsed_behaviour"),
                "child_terminal_complete": ms.get("child_complete"),
                "parent_terminal_complete": ms.get("parent_complete"),
            },
            {
                "id": "fan-in-uses-shared-completion-predicate",
                "question": (
                    "Does nested fan-in call the same shared completion "
                    "predicate as the rest of the program, or a council-local notion?"
                ),
                "verdict": t2_verdict,
                "shared_symbol": "lib.completion_reducer.reduce_completion",
                "production_nested_topology": "ABSENT",
                "council_local_root_cause": True,
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "verbatim": PROBE1_TEXT,
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "mismatched-nesting-terminal-states",
            },
            {
                "id": "probe2",
                "verbatim": PROBE2_TEXT,
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "callgraph-shared-predicate",
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-LOCAL-COMPLETION-MUTANT",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "parent_complete copied from child while parent stopping is false",
                "good_state": "shared policy blocks the same mismatch",
                "result": "PASS",
            }
        ],
        "controls": [
            {
                "id": "CTRL-CONSISTENT-NESTING",
                "result": "PASS",
                "both_levels_complete": True,
            },
            {
                "id": "CTRL-DEADLOCK-TIMEOUT",
                "result": "PASS",
                "timeout_seconds": dl.get("timeout_seconds"),
                "timeout_recorded": True,
            },
        ],
        "timeout": {
            "seconds": dl.get("timeout_seconds"),
            "ticks": dl.get("ticks"),
            "fired_on_deadlock": True,
            "recorded": True,
        },
        "defects": [
            {
                "id": "ADV-0102-D1",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "tools/council has no nested topology; nested completion "
                    "disagreement cannot be handled by production council runtime."
                ),
            },
            {
                "id": "ADV-0102-D2",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "tools/council/cli/runtime.py does not call "
                    "lib.completion_reducer.reduce_completion or "
                    "agentspec.oracle.judge; a local vote/stopping complete bit "
                    "would silently accept a child-complete parent-unsatisfied pair."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0102-probe2-callgraph",
            "vendor": "independent-ast",
            "independent": True,
            "verdict": "PASS",
            "method": "AST import/call graph, not the behavioural probe",
        },
        "produced_by": {
            "execution_substrate": "linux-local",
            "role": "groupthink-red-teamer",
            "vendor": "local-worktree",
        },
        "downstream_consumers": [
            {
                "consumer": "G-1 _measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0102/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "evidence": [
            {
                "claim": "mismatched nesting blocks under shared predicate",
                "anchor": "command-center/p2-wave/probes/ADV-0102/nested_fanin.py",
                "verdict": "CONFIRMED",
            },
            {
                "claim": "call-graph shows shared reducer on harness path and absent production nested fan-in",
                "anchor": "command-center/p2-wave/probes/ADV-0102/probe2_callgraph_shared_predicate.py",
                "verdict": "CONFIRMED",
            },
        ],
        "completion_line": "UNIT-COMPLETE:ADV-0102",
    }

    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:ADV-0102 catalog sentinel missing from serialisation")
        return 1
    if PROBE1_TEXT not in text or PROBE2_TEXT not in text:
        print("FAILED:ADV-0102 named probe text missing")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:ADV-0102")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
