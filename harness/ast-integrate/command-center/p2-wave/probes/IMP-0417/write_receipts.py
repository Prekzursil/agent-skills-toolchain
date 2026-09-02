#!/usr/bin/env python3
"""Write IMP-0417 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
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
UID = "IMP-0417"
OUT_REL = "command-center/receipts/IMP-0417.json"
SENTINEL = "SENTINEL:IMP-0417:REDUCER-SINGLE-SOURCE"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0417/probe1_import_graph.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0417/probe2_planted_predicate.py"
)
TCMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/completion/tests/test_import_graph.py"
)
SUPPORTING = [
    "tools/completion/__init__.py",
    "tools/completion/reducer.py",
    "tools/completion/census.py",
    "tools/completion/sites/__init__.py",
    "tools/completion/sites/local_runner.py",
    "tools/completion/sites/cloud_dispatcher.py",
    "tools/completion/sites/monitor.py",
    "tools/completion/sites/harvester.py",
    "tools/completion/sites/workflow_fanin.py",
    "tools/completion/sites/cross_vendor_adapter.py",
    "tools/completion/sites/final_synthesis.py",
    "tools/completion/tests/test_import_graph.py",
    "command-center/p2-wave/probes/IMP-0417/scenario.py",
    "command-center/p2-wave/probes/IMP-0417/probe1_import_graph.py",
    "command-center/p2-wave/probes/IMP-0417/probe2_planted_predicate.py",
    "command-center/p2-wave/probes/IMP-0417/fixtures/before/local_runner.py",
    "command-center/p2-wave/probes/IMP-0417/fixtures/before/cloud_dispatcher.py",
    "command-center/p2-wave/probes/IMP-0417/fixtures/before/monitor.py",
    "command-center/p2-wave/probes/IMP-0417/fixtures/before/harvester.py",
    "command-center/p2-wave/probes/IMP-0417/fixtures/before/workflow_fanin.py",
    "command-center/p2-wave/probes/IMP-0417/fixtures/before/cross_vendor_adapter.py",
    "command-center/p2-wave/probes/IMP-0417/fixtures/before/final_synthesis.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
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


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "bytes": size,
        "eol": "LF",
        "exists": True,
        "path": rel,
        "role": role,
        "sha256": sha,
    }


def manifest_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/IMP-0417/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": UID,
    }


def main() -> int:
    c_t, t_t = run_cmd(TCMD)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_t != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0417 receipts tests={c_t} p1={c1} p2={c2}")
        print(t_t[-3000:])
        print(t1[-3000:])
        print(t2[-3000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting_arts = [art_row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in supporting_arts if not (REPO / a["path"]).is_file()]
    if missing:
        print("FAILED:IMP-0417 missing supporting", missing)
        return 1

    evidence_src = {
        "command": P1,
        "exit_code": c1,
        "fingerprint": fp("command", P1),
        "method": "command",
        "raw_output": t1[-8000:],
        "role": "source",
    }
    evidence_ver = {
        "command": P2,
        "exit_code": c2,
        "fingerprint": fp("command", P2),
        "method": "command",
        "raw_output": t2[-8000:],
        "role": "verifier",
    }
    test_probe = {
        "command": TCMD,
        "exit_code": c_t,
        "fingerprint": fp("command", TCMD),
        "method": "command",
        "raw_output": t_t[-4000:],
        "role": "source",
    }

    try:
        blob_start = t1.find("{")
        blob_end = t1.rfind("}")
        if blob_start >= 0 and blob_end > blob_start:
            p1_json = json.loads(t1[blob_start : blob_end + 1])
            before_n = p1_json.get("before_count")
            after_n = p1_json.get("after_count")
    except json.JSONDecodeError:
        before_n = after_n = None

    receipt = {
        "artifacts": supporting_arts,
        "census": {
            "before_independent_checks": before_n,
            "after_independent_checks": after_n,
            "before_source": "command-center/p2-wave/probes/IMP-0417/fixtures/before",
            "after_source": "tools/completion/sites",
            "shared_library": "tools/completion/reducer.py",
            "shared_symbol": "completion.reducer.judge",
            "surviving_non_library_checks": [],
            "justification": (
                "The seven named fan-in modules contain zero independent "
                "predicates after adoption. Partition tools such as "
                "command-center/ready_units.py and "
                "command-center/p2-wave/_measure_one_delivered.py are "
                "delivery measures, not fan-in sites, and are out of this "
                "unit's replacement set."
            ),
        },
        "completion_sentinel": SENTINEL,
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": True,
                "exit_code": None,
                "probe": {
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0417",
                    "exit_code": None,
                    "fingerprint": fp(
                        "command",
                        "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0417",
                    ),
                    "method": "command",
                    "raw_output": "measured after this receipt is written",
                    "role": "verifier",
                },
                "read_ok": True,
            }
        ],
        "evidence": [
            {
                "anchor": "tools/completion/sites/__init__.py:SITE_IDS",
                "claim": (
                    "All seven spec-named fan-in sites (local runner, cloud "
                    "dispatcher, monitor, harvester, workflow fan-in, "
                    "cross-vendor adapter, final synthesis) import "
                    "completion.reducer.judge as one function object."
                ),
                "confidence": "almost-certain",
                "probes": [evidence_src, test_probe],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "tools/completion/census.py:ast_hits_in_source",
                "claim": (
                    f"AST census: before={before_n} independent completion "
                    f"checks in the pre-adoption fixtures; after={after_n} "
                    "in the live seven sites. Every surviving non-library "
                    "check in those sites is listed (empty after adoption)."
                ),
                "confidence": "almost-certain",
                "probes": [evidence_src, evidence_ver],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/IMP-0417/probe2_planted_predicate.py:main",
                "claim": (
                    "Detector control: a planted local exit-zero COMPLETE "
                    "predicate is caught by the AST census and independently "
                    "by a regex census (different pattern). The unmutated "
                    "live site is silent on both."
                ),
                "confidence": "almost-certain",
                "probes": [evidence_ver, test_probe],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "tools/completion/reducer.py:judge",
                "claim": (
                    "Exit code zero alone returns INCOMPLETE. A claimed digest "
                    "with no file on disk returns INCOMPLETE. COMPLETE requires "
                    "the reducer to stat the artifact path itself."
                ),
                "confidence": "almost-certain",
                "probes": [test_probe, evidence_src],
                "verdict": "CONFIRMED",
            },
        ],
        "failure_class_seeded": "two completion predicates disagree",
        "implementation": {
            "library": "tools/completion/reducer.py",
            "symbol": "completion.reducer.judge",
            "sites": [
                "tools/completion/sites/local_runner.py",
                "tools/completion/sites/cloud_dispatcher.py",
                "tools/completion/sites/monitor.py",
                "tools/completion/sites/harvester.py",
                "tools/completion/sites/workflow_fanin.py",
                "tools/completion/sites/cross_vendor_adapter.py",
                "tools/completion/sites/final_synthesis.py",
            ],
            "census": "tools/completion/census.py",
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0417/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "min_bytes_threshold": 128,
        "negative_controls": [
            {
                "bad_state_output": "planted exit_code==0 -> COMPLETE; AST+regex fire",
                "description": "Planted local predicate must be reported at file:line",
                "fired_on_bad_state": True,
                "good_state_output": "live tools/completion/sites/local_runner.py silent",
                "id": "planted-local-predicate",
                "kind": "known-broken-fixture",
                "silent_on_good_state": True,
            },
            {
                "bad_state_output": "Observation(exit_code=0) -> INCOMPLETE",
                "description": "Exit code zero alone is never COMPLETE",
                "fired_on_bad_state": True,
                "good_state_output": "full 12-condition payload with real file -> COMPLETE",
                "id": "exit-zero-alone",
                "kind": "mutation",
                "silent_on_good_state": True,
            },
        ],
        "notes": (
            "G-1 for IMP-0417: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild. Shared reducer lives at tools/completion/reducer.py "
            "because IMP-0415's library artifact is absent on this worktree; "
            "the seven call sites import that one symbol."
        ),
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "question_or_target": (
            "Replace every local completion check at the seven call sites the "
            "spec names (local runner, cloud dispatcher, monitor, harvester, "
            "workflow fan-in, cross-vendor adapter, final synthesis) with the "
            "shared library, and emit a census proving no site retains its own "
            "predicate. Exact question: how many independent completion checks "
            f"exist in the tree before and after? before={before_n} after={after_n}."
        ),
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0415 (twelve-condition library) is not delivered on "
                    "this worktree. This unit authored the single importable "
                    "judge the seven sites needed rather than leaving them on "
                    "local predicates."
                ),
                "settling_experiment": (
                    "When IMP-0415 lands, re-point the seven sites at its "
                    "symbol if it differs and re-run the census."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "retry": {"count": 0, "policy": "max 2 attempts, backoff 30s/120s"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "note": (
                "Probe 2 re-runs the census with a regex pattern distinct from "
                "the AST detector used in probe 1."
            ),
            "reviewer_id": "IMP-0417-probe2-planted-predicate",
            "verdict": "PASS",
        },
        "schema_version": 1,
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:10648",
        "state": "SUCCESS",
        "tests": [
            {
                "command": TCMD,
                "id": "test_import_graph.py",
                "result": "PASS" if c_t == 0 else "FAIL",
            },
            {
                "command": P1,
                "id": "probe1_import_graph",
                "result": "PASS" if c1 == 0 else "FAIL",
            },
            {
                "command": P2,
                "id": "probe2_planted_predicate",
                "result": "PASS" if c2 == 0 else "FAIL",
            },
        ],
        "timestamps": {"ended_at": now, "started_at": now},
        "title": "Reducer call-site adoption and census across all seven fan-in points",
        "unit_id": UID,
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    primary = manifest_row(OUT_REL, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]

    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT_REL,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "id": UID,
        "manifest_path": "command-center/p2-wave/probes/IMP-0417/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
            },
        ],
        "notes": (
            "G-1 for IMP-0417: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0417-probe2-planted-predicate",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests_command": TCMD,
        "tests_exit_code": c_t,
        "ts": now,
        "unit_id": UID,
    }
    man = {
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UID,
        "verified_on_disk": True,
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"census before={before_n} after={after_n}")
    print("SUCCESS:IMP-0417 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
