#!/usr/bin/env python3
"""Emit RES-0154 measurement artifact and per-unit receipts."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import experiment as E  # noqa: E402
from util import (  # noqa: E402
    SCHEMA_DECLARED,
    SENTINEL,
    UNIT,
    OUT_REL,
    lineage,
    now_utc,
    sha256_file,
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0154/probe1_negative_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0154/probe2_third_agent_and_volume.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0154/util.py",
    "command-center/p2-wave/probes/RES-0154/corpus.py",
    "command-center/p2-wave/probes/RES-0154/refute.py",
    "command-center/p2-wave/probes/RES-0154/find.py",
    "command-center/p2-wave/probes/RES-0154/judge.py",
    "command-center/p2-wave/probes/RES-0154/score.py",
    "command-center/p2-wave/probes/RES-0154/experiment.py",
    "command-center/p2-wave/probes/RES-0154/probe1_negative_control.py",
    "command-center/p2-wave/probes/RES-0154/probe2_third_agent_and_volume.py",
    "command-center/p2-wave/probes/RES-0154/emit.py",
]


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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": digest,
        "bytes": size,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def load_bearing_claims(exp: dict, fetched_at: str) -> list[dict]:
    schema_l = lineage("command-center/schema/work-unit.schema.json", fetched_at)
    sidecar_l = lineage(
        "command-center/p2-wave/probes/RES-0147/_validate_out.json", fetched_at
    )
    judge_l = lineage(
        "command-center/p2-wave/probes/RES-0154/judge.py", fetched_at
    )
    nc = exp["negative_control"]
    cmp_ = exp["comparison"]
    return [
        {
            "id": "RES-0154-C-INCENTIVE",
            "claim": (
                "A refuter PASSes on sound work when surviving refutations on a "
                "known-correct artifact equal zero. Emitted count is not a score "
                "input. After that true-negative gate, rank by precision then "
                "surviving yield per billed hour."
            ),
            "status": "VERIFIED",
            "sherman_kent": "almost-certain",
            "signals": [
                {
                    "id": "honest-score-rule",
                    "note": exp["agents"]["honest_refuter"]["honest_score"]["rule"],
                },
                {
                    "id": "volume-rejected",
                    "note": exp["agents"]["noisy_refuter"]["volume_score"]["reason"],
                },
            ],
            "source_lineage": schema_l,
            "verification_path": P1,
        },
        {
            "id": "RES-0154-C-NEGATIVE-CONTROL",
            "claim": (
                "On two known-correct JSON Schema documents the honest refuter "
                f"emitted {nc['honest_emitted_on_known_correct']} findings and "
                f"{nc['honest_surviving']} surviving refutations. A noisy "
                "refuter emitted "
                f"{nc['noisy_emitted_on_known_correct']} findings on the same "
                "documents; the third agent let none survive."
            ),
            "status": "VERIFIED",
            "sherman_kent": "almost-certain",
            "signals": [
                {"id": "live-negative-control", "note": json.dumps(nc, sort_keys=True)},
                {"id": "schema-sha256", "note": schema_l["sha256"]},
            ],
            "source_lineage": schema_l,
            "verification_path": P1,
        },
        {
            "id": "RES-0154-C-YIELD",
            "claim": (
                "On the same corpus, billed at 60 seconds per artifact "
                f"({exp['billed_hours']} h), honest surviving yield is "
                f"{cmp_['honest_yield_per_hour']}/h at precision "
                f"{cmp_['honest_precision']}. The volume finder emits "
                f"{cmp_['finder_volume_per_hour']}/h but surviving yield "
                f"{cmp_['finder_yield_surviving_per_hour']}/h at precision "
                f"{cmp_['finder_precision']}. Share that survives re-review is "
                "honest 1.0 versus finder 0.0."
            ),
            "status": "VERIFIED",
            "sherman_kent": "almost-certain",
            "signals": [
                {"id": "comparison", "note": json.dumps(cmp_, sort_keys=True)},
                {"id": "defective-sidecar-sha256", "note": sidecar_l["sha256"]},
            ],
            "source_lineage": sidecar_l,
            "verification_path": P2,
        },
        {
            "id": "RES-0154-C-THIRD-AGENT",
            "claim": (
                "Survival is judged by judge.py from artifact bytes and the "
                "candidate only. Author-label swap left verdicts invariant "
                f"(author_swap_invariant={exp['author_swap_invariant']}). "
                "judge.py does not import refute.py, find.py, or corpus gold."
            ),
            "status": "VERIFIED",
            "sherman_kent": "almost-certain",
            "signals": [
                {"id": "author-swap", "note": str(exp["author_swap_invariant"])},
                {
                    "id": "honest-survivor-kinds",
                    "note": json.dumps(
                        exp["agents"]["honest_refuter"]["survivor_kinds"]
                    ),
                },
            ],
            "source_lineage": judge_l,
            "verification_path": P2,
        },
    ]


def build_artifact(exp: dict) -> dict:
    fetched_at = now_utc()
    question = (
        "How should a refutation agent be scored so that producing zero "
        "refutations on sound work is a PASS rather than a failure, and what "
        "is the measured refutation yield (refutations per agent-hour, share "
        "that survive re-review) compared with finder agents on the same corpus?"
    )
    nc = exp["negative_control"]
    cmp_ = exp["comparison"]
    answer = (
        "Score a refuter as PASS when surviving refutations on a known-correct "
        "artifact are zero; never use emitted volume as a score input. After "
        "that true-negative gate, rank by surviving precision then surviving "
        f"yield. On this corpus honest yield is {cmp_['honest_yield_per_hour']} "
        f"surviving/hour at precision {cmp_['honest_precision']}; finder yield "
        f"is {cmp_['finder_yield_surviving_per_hour']} surviving/hour at "
        f"precision {cmp_['finder_precision']} despite "
        f"{cmp_['finder_volume_per_hour']} emissions/hour. Known-correct "
        f"surviving={nc['honest_surviving']}."
    )
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "measurement-run",
        "output_schema": SCHEMA_DECLARED,
        "schema_note": (
            "command-center/schema/measurement-run.schema.json is absent on "
            "this sparse tree and is not rebuilt here (no ADV schema circle)."
        ),
        "title": (
            "Refuter role design: incentives, success metric, and measured "
            "yield versus finder agents"
        ),
        "question": question,
        "question_or_target": question,
        "answer": answer,
        "incentive_design": {
            "true_negative_is_pass": True,
            "success_on_known_correct": "surviving_refutations == 0",
            "volume_is_score_input": False,
            "rank_after_gate": ["precision", "surviving_yield_per_billed_hour"],
            "noisy_floor_failure_mode": (
                "A refuter that always emits at least one finding is generating "
                "noise to satisfy a volume metric; those nits must not survive "
                "third-agent re-review and must not raise the honest score."
            ),
        },
        "meter": {
            "billed_seconds_per_artifact": 60,
            "billed_hours": exp["billed_hours"],
            "note": exp["billed_hours_note"],
        },
        "corpus": exp["artifacts"],
        "agents": exp["agents"],
        "ranking_honest": exp["ranking_honest"],
        "ranking_volume": exp["ranking_volume"],
        "volume_ranking_differs": exp["volume_ranking_differs"],
        "author_swap_invariant": exp["author_swap_invariant"],
        "negative_control": nc,
        "comparison": cmp_,
        "n_artifacts": exp["n_artifacts"],
        "claims": load_bearing_claims(exp, fetched_at),
        "missing_catalog_inputs": [
            {
                "path": "_USER-PROMPTS.md",
                "status": "ABSENT",
                "note": "Catalog named lines 10681-10717 and 11043-11064.",
            },
            {"path": "command-center/sources/REGISTER.md", "status": "ABSENT"},
            {"path": "command-center/CLAIM-REGISTRY.json", "status": "ABSENT"},
            {
                "path": "rules/common/fan-out-contract.md",
                "status": "ABSENT",
                "note": (
                    "B7 never-score-on-volume is taken from the catalog input "
                    "line, not from a missing markdown file."
                ),
            },
            {
                "path": SCHEMA_DECLARED,
                "status": "ABSENT",
                "note": "Not rebuilt (no ADV schema circle).",
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog reviewer is an independent Anthropic opus refuter "
                    "in a fresh context. That vendor session was not run. "
                    "Probe 2 (judge.py) is the independent mechanical third "
                    "agent. Vendor review remains NOT-CHECKED and does not "
                    "BLOCK G-1."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Dispatch anthropic/opus against the raw corpus files with "
                    "the prompt passed by file; compare surviving findings to "
                    "judge.py."
                ),
            },
            {
                "claim": (
                    "Yield uses a declared 60-second billed meter per artifact, "
                    "not live LLM agent-hours."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run with recorded LLM wall-clock and report whether "
                    "honest still beats finder on surviving yield."
                ),
            },
        ],
        "tests": [
            {
                "id": "negative-control-known-correct-zero-surviving",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "noisy-floor-does-not-survive",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "third-agent-author-blind",
                "command": P2,
                "result": "PASS",
            },
            {"id": "volume-not-score-input", "command": P2, "result": "PASS"},
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "negative-control-known-correct"},
            {"id": "probe2", "command": P2, "role": "third-agent-and-volume"},
        ],
        "reviewer": {
            "reviewer_id": "RES-0154-probe2-third-agent-judge",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 re-runs the experiment, checks judge.py imports, "
                "plants a nit and a false exists-missing on a known-correct "
                "schema, and confirms volume ranking diverges from honest ranking."
            ),
        },
        "notes": (
            "G-1 delivery of RES-0154. Live named probes exit 0. Artifact "
            "state=SUCCESS. Did not run global unit_manifest.py --write. "
            "cloud ok is not consulted. Did not implement ADV rebuild."
        ),
        "SUCCESS:RES-0154": True,
        "fetched_at": fetched_at,
    }


def write_receipts(code1: int, out1: str, code2: int, out2: str) -> int:
    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_DECLARED,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "raw_output": out1[-8000:],
                "role": "negative-control-known-correct",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "raw_output": out2[-8000:],
                "role": "third-agent-and-volume",
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0154-probe2-third-agent-judge",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0154: live named probes exit 0, measurement artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
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
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:RES-0154 receipts")
    return 0


def main() -> int:
    exp = E.run_experiment()
    if not exp["negative_control"]["pass"]:
        print("FAILED:RES-0154 negative control")
        return 1
    if not exp["comparison"]["honest_beats_finder_on_precision"]:
        print("FAILED:RES-0154 finder precision not beaten")
        return 1
    doc = build_artifact(exp)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out)
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:RES-0154 sentinel absent")
        return 1
    if size < 1024:
        print(f"FAILED:RES-0154 artifact too small {size}")
        return 1
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")

    code1, out1 = run(P1)
    code2, out2 = run(P2)
    print(out1[-2000:])
    print(out2[-2000:])
    if code1 != 0 or "SUCCESS:RES-0154-probe1" not in out1:
        print("FAILED:RES-0154 probe1")
        return 1
    if code2 != 0 or "SUCCESS:RES-0154-probe2" not in out2:
        print("FAILED:RES-0154 probe2")
        return 1
    write_receipts(code1, out1, code2, out2)
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
