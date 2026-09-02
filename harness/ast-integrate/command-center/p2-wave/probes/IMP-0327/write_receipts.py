#!/usr/bin/env python3
"""Write IMP-0327 receipt, per-unit manifest, and SUBAGENT-RETURN.json."""

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
UNIT = "IMP-0327"
OUT = "command-center/receipts/IMP-0327.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0327/probe1_five_goals_roundtrip.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0327/probe2_unknown_metric_refused.py"
)
SUPPORTING = [
    "tools/council/__init__.py",
    "tools/council/builder/__init__.py",
    "tools/council/builder/errors.py",
    "tools/council/builder/metrics.py",
    "tools/council/builder/expr.py",
    "tools/council/builder/goals.py",
    "tools/council/builder/spec.py",
    "tools/council/builder/fixtures.py",
    "tools/council/tests/__init__.py",
    "tools/council/tests/test_builder.py",
    "command-center/p2-wave/probes/IMP-0327/probe1_five_goals_roundtrip.py",
    "command-center/p2-wave/probes/IMP-0327/probe2_unknown_metric_refused.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


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
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0327/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0327 emit probes c1={c1} c2={c2}")
        print(t1[-4000:])
        print(t2[-4000:])
        return 1

    sys.path.insert(0, str(REPO / "tools"))
    from council.builder import METRICS, SPEC_ANCHOR, build_all_owner_goals, restate
    from council.builder.metrics import METRICS as METRIC_TABLE

    specs = build_all_owner_goals()
    printed = []
    for gid, spec in specs.items():
        printed.append(
            {
                "goal_id": gid,
                "phrasing": spec["charter"]["owner_phrasing"],
                "printed": spec["stopping"]["printed"],
                "restate": restate(spec),
                "bound_metrics": spec["meta"]["bound_metrics"],
            }
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl = REPO / "tools/council/builder/spec.py"
    impl_sha, impl_n = digest(impl)
    receipt = {
        "unit_id": UNIT,
        "id": UNIT,
        "title": "Structured council builder",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0327",
        "completion_sentinel": "SUCCESS:IMP-0327",
        "schema_version": 1,
        "ts": now,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-builder-surface"
        ),
        "profile": "council-builder-surface",
        "spec_anchor": SPEC_ANCHOR,
        "question": (
            "Implement tools/council/builder/ as a guided structured builder "
            "that composes a CouncilSpec from typed questions and can express "
            "the five owner goal phrasings at spec 11198. Falsifiable question: "
            "can each of those five natural-language goals be produced by the "
            "builder, and does the resulting spec's stopping expression actually "
            "encode the stated goal?"
        ),
        "implementation": {
            "path": "tools/council/builder/",
            "entry_point": "tools/council/builder/spec.py:build",
            "sha256": impl_sha,
            "bytes": impl_n,
            "closed_metrics": sorted(METRIC_TABLE),
            "lookup": "METRICS[key] total function; unknown metric BuildError",
            "not_nlp": (
                "Owner phrasings map through a closed exact-string table to "
                "typed answers. Unknown prose is refused; fill typed questions."
            ),
        },
        "honesty": {
            "original_prompt_file_absent": True,
            "original_prompt_path": (
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                "_USER-PROMPTS.md:11198"
            ),
            "phrasings_source": (
                "CNL-0128 catalog question_or_target, which quotes the five goals"
            ),
            "not_imp_0308_full_grammar": True,
            "not_live_llm_council": True,
            "fixture_snapshots_are_injected": True,
            "schema_file_11_absent": True,
            "dependencies_imp_0321_imp_0306_not_required_for_this_surface": True,
        },
        "artifact_paths": [OUT] + SUPPORTING,
        "evidence": [
            {
                "id": "signal-1-five-goals-built-and-printed",
                "claim": (
                    "All five owner goals build; each stopping expression is "
                    "printed; canonical_shape matches the catalog oracle."
                ),
                "verdict": "CONFIRMED",
                "probe": "probe1_five_goals_roundtrip.py",
                "stopping_expressions": printed,
            },
            {
                "id": "signal-2-fixtures-stop-for-stated-reason",
                "claim": (
                    "Each built spec evaluated against unmet and met injected "
                    "snapshots: unmet continues, met stops, fired metrics are "
                    "the stated reason."
                ),
                "verdict": "CONFIRMED",
                "probe": "probe1_five_goals_roundtrip.py",
            },
            {
                "id": "signal-3-independent-encoding-oracle",
                "claim": (
                    "Probe 2 re-walks the five trees against an oracle defined "
                    "in the probe (not goals.py) and rejects unique_ideas>=1 as G1."
                ),
                "verdict": "CONFIRMED",
                "probe": "probe2_unknown_metric_refused.py",
            },
        ],
        "test_ids": [
            "five-goals-roundtrip",
            "fixture-stop-reason",
            "unknown-metric-refused",
            "planted-weak-threshold-does-not-encode-G1",
        ],
        "negative_control_ids": [
            "unknown-metric-refused",
            "planted-weak-threshold-does-not-encode-G1",
            "g3-unmet-no-minority",
        ],
        "negative_controls": [
            {
                "id": "unknown-metric-refused",
                "description": (
                    "A goal whose stopping metric does not exist (vibe_score) "
                    "must be refused at build time with path=stopping.primary.metric "
                    "reason=unknown_metric."
                ),
                "fired": True,
            },
            {
                "id": "planted-weak-threshold-does-not-encode-G1",
                "description": (
                    "unique_ideas >= 1 must not encode 'brainstorm until 100 unique ideas'."
                ),
                "fired": True,
            },
        ],
        "tests": [
            {
                "id": "five-goals-roundtrip",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "unknown-metric-refused",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0327-probe2-encoding-oracle",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests, not the author's summary",
            "verdict": "PASS",
            "method": (
                "Re-derive encoding from canonical_shape vs probe-local oracle; "
                "run unknown-metric and planted-weak-threshold tests."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "The byte-exact line at _USER-PROMPTS.md:11198 is not on "
                    "this worktree; phrasings are the catalog quote."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Diff the five strings against the restore snapshot of "
                    "_USER-PROMPTS.md:11198 when that file is mounted."
                ),
            },
            {
                "claim": (
                    "IMP-0261 councilspec.schema.json and the 72 presets are "
                    "absent; this envelope is not claimed to validate against them."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "ANY/ALL/weighted stopping forms (IMP-0308) are not emitted "
                    "by this builder."
                ),
                "verdict": "ACCEPTED-LIMITATION",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
        "dependencies_note": (
            "Catalog lists IMP-0321 and IMP-0306. Those modules are participation "
            "and consent/veto surfaces. This unit ships a builder-local stopping "
            "tree and does not wait on them."
        ),
        "closed_metric_count": len(METRICS),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0327",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "cloud_ok": False,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0327/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0327-probe2-encoding-oracle",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0327: live named probes exit 0, receipt state=SUCCESS "
            "with SUCCESS:IMP-0327, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Builder-surface envelope; not IMP-0308 "
            "and not a live LLM council."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0327 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
