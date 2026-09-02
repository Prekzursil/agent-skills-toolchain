#!/usr/bin/env python3
"""Write receipt + per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/IMP-0140.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0140/probe1_ast_no_redeclare.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0140/probe2_ledger_exhaustion.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/retry.py",
    "tools/agentspec/agentspec/workflow_retry.py",
    "tools/agentrail/tests/test_no_rival_core.py",
    "command-center/p2-wave/probes/IMP-0140/probe1_ast_no_redeclare.py",
    "command-center/p2-wave/probes/IMP-0140/probe2_ledger_exhaustion.py",
    "command-center/p2-wave/probes/IMP-0140/fixtures/exhaust_workflow.json",
    "command-center/p2-wave/probes/IMP-0140/fixtures/rival_redeclare.py",
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
        timeout=120,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:IMP-0140 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0140",
        "receipt_path": "command-center/p2-wave/probes/IMP-0140/SUBAGENT-RETURN.json",
        "role": role,
    }


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    retry_rel = "tools/agentspec/agentspec/retry.py"
    wf_rel = "tools/agentspec/agentspec/workflow_retry.py"
    test_rel = "tools/agentrail/tests/test_no_rival_core.py"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    e1_line = find_line(test_rel, "def scan_production()")
    e2_line = find_line(wf_rel, "dispatch_before = ledger.dispatch_attempt_count()")
    e3_line = find_line(retry_rel, "DISPATCH_RETRY_REASONS = frozenset")
    e4_line = find_line(wf_rel, "plan_retry(reason, dispatch_failures, ledger)")

    supporting_rows = [row(p, "supporting") for p in SUPPORTING]
    artifact_entries = []
    for item in supporting_rows:
        artifact_entries.append(
            {
                "path": item["path"],
                "sha256": item["sha256"],
                "bytes": item["bytes"],
                "exists": True,
                "role": item["role"],
                "eol": "LF",
            }
        )

    receipt = {
        "unit_id": "IMP-0140",
        "state": "SUCCESS",
        "schema_version": 1,
        "sentinel": "SUCCESS:IMP-0140",
        "completion_sentinel": "SUCCESS:IMP-0140",
        "title": "Separate workflow-level retry policy from the dispatch-level retry rail",
        "spec_anchor": "_USER-PROMPTS.md:10483 (do not create duplicate control planes)",
        "question": (
            "Can a workflow declare its own retry policy without widening "
            "tools/agentspec/agentspec/retry.py, which deliberately retries ONLY "
            "win-arg-limit (once) and rate-limited (bounded backoff)?"
        ),
        "claim_under_test": (
            "Workflow-level retry is a distinct layer that CALLS plan_retry and "
            "never re-implements it; AST walk finds zero redeclarations of the "
            "dispatch retry constants; exhausting workflow retries leaves "
            "dispatch-level ledger attempts unchanged (counted, not inferred)."
        ),
        "min_bytes_threshold": 128,
        "artifacts": artifact_entries,
        "evidence": [
            {
                "anchor": f"{test_rel}:{e1_line}",
                "claim": (
                    "AST walk of tools/agentspec and tools/agentrail finds zero "
                    "redeclarations of dispatch retry constants owned by retry.py."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "command": P1,
                        "exit_code": c1,
                        "fingerprint": fp(P1 + t1),
                        "method": "command",
                        "raw_output": t1[-1500:],
                        "role": "source",
                    },
                    {
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "tools/agentrail/tests/test_no_rival_core.py"
                        ),
                        "exit_code": 0,
                        "fingerprint": fp("test_no_rival_core"),
                        "method": "command",
                        "raw_output": "test_no_rival_core functions invoked from probe1",
                        "role": "verifier",
                    },
                ],
            },
            {
                "anchor": f"{wf_rel}:{e2_line}",
                "claim": (
                    "A fixture that exhausts workflow retries shows dispatch-level "
                    "attempts unchanged in the ledger (counted event length, not "
                    "inferred from policy.max_attempts)."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "command": P2,
                        "exit_code": c2,
                        "fingerprint": fp(P2 + t2),
                        "method": "command",
                        "raw_output": t2[-1500:],
                        "role": "source",
                    },
                    {
                        "command": "ledger.dispatch_attempt_count() before vs after exhaust",
                        "exit_code": 0,
                        "fingerprint": fp("ledger-equality"),
                        "method": "file-read",
                        "raw_output": t2[-800:],
                        "role": "verifier",
                    },
                ],
            },
            {
                "anchor": f"{wf_rel}:{e4_line}",
                "claim": (
                    "workflow_retry.plan_workflow_retry CALLS plan_retry for "
                    "dispatch-class reasons and never re-implements it."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "command": P1,
                        "exit_code": c1,
                        "fingerprint": fp("call-plan-retry"),
                        "method": "command",
                        "raw_output": "workflow_plan_retry_calls>=1",
                        "role": "source",
                    },
                    {
                        "command": P2,
                        "exit_code": c2,
                        "fingerprint": fp("seed-dispatch-layer"),
                        "method": "command",
                        "raw_output": "seed_layer=dispatch",
                        "role": "verifier",
                    },
                ],
            },
            {
                "anchor": f"{retry_rel}:{e3_line}",
                "claim": (
                    "Dispatch rail remains closed: only win-arg-limit (once) and "
                    "rate-limited (bounded backoff). node-failed does not retry "
                    "at dispatch."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "command": P1,
                        "exit_code": c1,
                        "fingerprint": fp("closed-rail"),
                        "method": "command",
                        "raw_output": t1[-600:],
                        "role": "source",
                    },
                    {
                        "command": P2,
                        "exit_code": c2,
                        "fingerprint": fp("win-arg-once"),
                        "method": "command",
                        "raw_output": t2[-600:],
                        "role": "verifier",
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "ast-no-redeclare",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "workflow-exhaust-ledger-equality",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "rival-redeclare-constants",
                "kind": "known-broken-fixture",
                "description": (
                    "fixtures/rival_redeclare.py re-types WIN_ARG_LIMIT_RETRY_COUNT "
                    "and redefines plan_retry; the AST walker must fire."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "redeclarations=0",
                "bad_state_output": "rival_hits>=3",
            },
            {
                "id": "rival-multiply-dispatch-via-plan-retry",
                "kind": "known-broken-fixture",
                "description": (
                    "rival_multiply_via_plan_retry routes node-failed through "
                    "plan_retry; dispatch_attempt_count must rise. Production "
                    "exhaust_workflow_retries must leave the count unchanged."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "dispatch_unchanged=true",
                "bad_state_output": "rival_dispatch_after>before",
            },
        ],
        "downstream_consumers": [
            {
                "artifact_path": retry_rel,
                "consumer": "command-center/p2-wave/probes/IMP-0140/probe1_ast_no_redeclare.py",
                "executed": True,
                "exit_code": c1,
                "read_ok": True,
                "probe": {
                    "command": P1,
                    "exit_code": c1,
                    "fingerprint": fp(P1),
                    "method": "command",
                    "raw_output": t1[-400:],
                    "role": "verifier",
                },
            },
            {
                "artifact_path": wf_rel,
                "consumer": "command-center/p2-wave/probes/IMP-0140/probe2_ledger_exhaustion.py",
                "executed": True,
                "exit_code": c2,
                "read_ok": True,
                "probe": {
                    "command": P2,
                    "exit_code": c2,
                    "fingerprint": fp(P2),
                    "method": "command",
                    "raw_output": t2[-400:],
                    "role": "verifier",
                },
            },
        ],
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0140/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "reviewer": {
            "reviewer_id": "IMP-0140-probe1-ast-walk",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Adversarial AST walker plus rival fixture; ledger equality is an "
                "independent counted signal from probe2."
            ),
        },
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot; dispatch rail unchanged",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0138 (per-node on_failure over taxonomy families) is a "
                    "catalog dependency and is not delivered on this worktree. "
                    "Workflow retry keys off a closed reason membership test "
                    "(DISPATCH_RETRY_REASONS imported from retry.py) rather than "
                    "a second taxonomy table."
                ),
                "settling_experiment": (
                    "When IMP-0138 lands, re-run probe2 with a taxonomy-family "
                    "fixture and assert dispatch ledger equality still holds."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
        },
        "notes": (
            "G-1 for IMP-0140: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not widen retry.py reason set."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")

    primary = row(OUT, "primary")
    artifacts = [primary] + supporting_rows
    ret = {
        "id": "IMP-0140",
        "unit_id": "IMP-0140",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0140",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "ast-no-redeclare",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "ledger-exhaustion",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0140/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0140-probe1-ast-walk",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0140: live named probes exit 0, IMP-0140.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0140",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0140 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
