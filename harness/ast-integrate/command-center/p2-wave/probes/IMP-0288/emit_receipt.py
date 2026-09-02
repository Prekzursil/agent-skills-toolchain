#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0288.json from live nested topology runs."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.council.topology import nested as N  # noqa: E402
from tools.council.shared_completion import judge as shared_judge  # noqa: E402
import call_graph as CG  # noqa: E402

OUT = "command-center/receipts/IMP-0288.json"
NESTED = "tools/council/topology/nested.py"
REDUCER = "tools/council/shared_completion.py"
FIXTURE = "command-center/p2-wave/probes/IMP-0288/fixtures/disagreement.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0288/probe1_nested_disagreement.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0288/probe2_resolution_rule_control.py"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:IMP-0288 emit missing snippet {snippet!r} in {path}")


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd, cwd=str(REPO), shell=True, capture_output=True, text=True
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def load_fixture() -> dict:
    return json.loads((REPO / FIXTURE).read_text(encoding="utf-8"))


def question(doc: dict, key: str) -> N.BoundedQuestion:
    raw = doc["questions"][key]
    return N.BoundedQuestion(
        question_id=raw["question_id"],
        prompt=raw["prompt"],
        max_rounds=int(raw["max_rounds"]),
    )


def main() -> int:
    doc = load_fixture()
    leaf_q = question(doc, "leaf")
    mid_q = question(doc, "mid")
    a = doc["parent_complete_child_incomplete"]
    kr = N.InMemoryKernel()
    res_a = N.run_nested(
        parent=a["parent"],
        question=leaf_q,
        child_artifact=a["child"],
        kernel=kr,
        apply_resolution_rule=True,
    )
    d2 = doc["depth2"]
    kr2 = N.InMemoryKernel()
    both = N.run_depth2(
        grandparent=d2["grandparent"],
        mid=d2["mid"],
        leaf=d2["leaf"],
        mid_question=mid_q,
        leaf_question=leaf_q,
        kernel=kr2,
        apply_resolution_rule=True,
    )
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0288 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    nested_path = REPO / NESTED
    reducer_path = REPO / REDUCER
    nested_sha, nested_bytes = digest(nested_path)
    reducer_sha, reducer_bytes = digest(reducer_path)
    fixture_sha, fixture_bytes = digest(REPO / FIXTURE)
    cg = CG.child_boundary_calls_shared_reducer()
    mutant = CG.mutant_drops_reducer()
    rule_line = find_line(nested_path, 'RESOLUTION_RULE_ID = "nested.disagreement')
    child_fn_line = find_line(nested_path, "def _judge_at_child_boundary")
    child_call_line = find_line(
        nested_path, 'return shared_judge(artifact, locus="child-boundary")'
    )
    resolve_line = find_line(nested_path, "def resolve_disagreement")
    judge_line = find_line(reducer_path, "def judge(")
    child_rejudge = shared_judge(a["child"], locus="receipt-rejudge")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    boundary = N.reducer_invocations(kr.events)

    receipt = {
        "unit_id": "IMP-0288",
        "id": "IMP-0288",
        "title": "Nested subcouncil spawn and fan-in",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "council-topology-module",
        "profile": "council-topology-module",
        "sentinel": "SUCCESS:IMP-0288",
        "completion_sentinel": "SUCCESS:IMP-0288",
        "min_bytes_threshold": 2048,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-topology-module"
        ),
        "spec_anchor": (
            "_USER-PROMPTS.md:11343 nested councils disagree on completion; "
            "catalog IMP-0288: spawn a subcouncil for a bounded question and "
            "fold its result back"
        ),
        "question_or_target": (
            "When parent and child disagree on completion, which one wins, "
            "and is that resolution explicit rather than incidental?"
        ),
        "answer": {
            "who_wins": (
                "The incomplete side blocks. Folded completion is COMPLETE iff "
                "the shared reducer says COMPLETE at the child boundary AND "
                "COMPLETE on the parent after fold "
                f"({N.RESOLUTION_RULE_ID})."
            ),
            "explicit": True,
            "incidental": False,
            "rule_id": N.RESOLUTION_RULE_ID,
            "not": [
                "last-writer-wins by processing order",
                "average/majority of self_report_complete bits",
                "child self-report as the completion signal",
            ],
        },
        "artifact_paths": [
            NESTED,
            REDUCER,
            FIXTURE,
            OUT,
        ],
        "artifacts": [
            {
                "path": NESTED,
                "sha256": nested_sha,
                "bytes": nested_bytes,
                "role": "implementation",
            },
            {
                "path": REDUCER,
                "sha256": reducer_sha,
                "bytes": reducer_bytes,
                "role": "child-boundary-reducer-seam",
            },
            {
                "path": FIXTURE,
                "sha256": fixture_sha,
                "bytes": fixture_bytes,
                "role": "disagreement-fixture",
            },
        ],
        "evidence": [
            {
                "id": "E1-disagreement-resolution-rule-id",
                "claim": (
                    "A parent-COMPLETE / child-INCOMPLETE fixture folds to "
                    "INCOMPLETE and records the deciding rule id."
                ),
                "path": NESTED,
                "line": rule_line,
                "snippet": N.RESOLUTION_RULE_ID,
                "observation": {
                    "parent_complete": res_a.resolution.parent.complete,
                    "child_complete": res_a.spawn.child_verdict.complete,
                    "winner_complete": res_a.resolution.winner_complete,
                    "blocking_party": res_a.resolution.blocking_party,
                    "rule_id": res_a.resolution.rule_id,
                    "incidental": res_a.resolution.incidental,
                    "dissent_ids": [
                        d.get("id")
                        for d in (res_a.parent.get("dissent") or [])
                        if isinstance(d, dict)
                    ],
                    "child_evidence_cited": res_a.parent.get("child_evidence_cited"),
                },
            },
            {
                "id": "E2-shared-reducer-child-boundary-call-graph",
                "claim": (
                    "_judge_at_child_boundary calls shared_judge; a planted "
                    "self_report_complete return makes the call-graph check fail."
                ),
                "path": NESTED,
                "line": child_call_line,
                "snippet": 'return shared_judge(artifact, locus="child-boundary")',
                "function_line": child_fn_line,
                "reducer_path": REDUCER,
                "reducer_line": judge_line,
                "kernel_trace": boundary,
                "call_graph": cg,
                "planted_rival": mutant,
                "child_self_report_complete": a["child"].get("self_report_complete"),
                "child_reducer_complete": child_rejudge.complete,
                "child_reducer_reason": child_rejudge.reason,
            },
            {
                "id": "E3-depth2-nesting",
                "claim": "Grandparent/mid COMPLETE + leaf BLOCKED stays INCOMPLETE at both folds.",
                "path": NESTED,
                "line": find_line(nested_path, "def run_depth2"),
                "inner_winner_complete": both["inner"].resolution.winner_complete,
                "outer_winner_complete": both["outer"].resolution.winner_complete,
                "inner_rule_id": both["inner"].resolution.rule_id,
                "outer_rule_id": both["outer"].resolution.rule_id,
                "child_boundary_judges": [
                    e.get("kind") for e in kr2.events
                ].count("CHILD_BOUNDARY_JUDGE"),
            },
        ],
        "test_ids": [
            "IMP-0288/probe1_nested_disagreement.py",
            "IMP-0288/probe2_resolution_rule_control.py",
            "integration:2-level-nesting-deliberate-completion-disagreement",
        ],
        "negative_control_ids": [
            "spec-11343-nested-disagreement:remove-resolution-rule-becomes-nondeterministic",
            "planted-rival-predicate:self_report_complete-skips-shared-judge",
        ],
        "reviewer_verdict": {
            "verdict": "PASS",
            "reviewer_id": "IMP-0288-probe2-resolution-rule-control",
            "independent": True,
            "started_from": "tests (negative control), not the author's summary",
            "notes": (
                "Probe 2 does not trust nested.py's docstring: it removes the "
                "resolution rule and requires the disagreement fixture to flip "
                "across processing orders, and requires the rule-on path to stay "
                "INCOMPLETE (no averaging)."
            ),
        },
        "residual_unknowns": [
            (
                "CC-0003 / agentspec.oracle.judge is not on this worktree; "
                "nested binds tools.council.shared_completion.judge, which "
                "delegates to the oracle when importable. Residual: the "
                "program-wide 12-condition oracle is not claimed delivered."
            ),
            (
                "IMP-0264 tools/council/kernel.py is not on this worktree; "
                "nested records SPAWN/TURN/CHILD_BOUNDARY_JUDGE/FOLD/RESOLUTION "
                "on InMemoryKernel (or Kernel() if later importable). Residual: "
                "the full round scheduler is not claimed delivered."
            ),
            (
                "No fresh-context human/cross-vendor reviewer was dispatched; "
                "the adversarial check is the live negative-control probe."
            ),
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
        "probe_tails": {
            "probe1": t1.splitlines()[-6:],
            "probe2": t2.splitlines()[-6:],
        },
        "dependencies_on_disk": {
            "IMP-0264_kernel": (REPO / "tools/council/kernel.py").is_file(),
            "IMP-0226_oracle": False,
            "shared_completion_seam": reducer_path.is_file(),
        },
        "ts": now,
        "notes": (
            "G-1 IMP-0288: nested spawn/fan-in with explicit conservative "
            "conjunction on parent/child completion disagreement. Live named "
            "probes exit 0. Did not run global unit_manifest.py --write."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0288" not in text:
        print("FAILED:IMP-0288 emit sentinel missing from receipt text")
        return 1
    out_path.write_text(text, encoding="utf-8")
    sha, size = digest(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0288")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
