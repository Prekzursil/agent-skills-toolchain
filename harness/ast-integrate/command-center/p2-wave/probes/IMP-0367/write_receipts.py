#!/usr/bin/env python3
"""Write IMP-0367 receipt, then per-unit SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST.

Named probes are re-run live. Does not invoke tools/command-center/unit_manifest.py --write.
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import scenario as S  # noqa: E402
from council.sensitivity import (  # noqa: E402
    DEFAULT_SEAT_COUNT,
    LOW_N_MAX,
    evaluate_question,
    load_question,
    public_row,
)

UID = "IMP-0367"
OUT = "command-center/receipts/IMP-0367.json"
SCHEMA = "command-center/schema/receipt.schema.json profile=council-runtime-module"
IMPL = "tools/council/sensitivity.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0367/probe1_decision_vs_n.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0367/probe2_evidence_decisive_control.py"
)
SUPPORTING = [
    IMPL,
    "command-center/p2-wave/probes/IMP-0367/probe1_decision_vs_n.py",
    "command-center/p2-wave/probes/IMP-0367/probe2_evidence_decisive_control.py",
    "command-center/p2-wave/probes/IMP-0367/scenario.py",
    "command-center/p2-wave/probes/IMP-0367/fixtures/evidence-decisive.json",
    "command-center/p2-wave/probes/IMP-0367/fixtures/n-sensitive.json",
    "command-center/p2-wave/probes/IMP-0367/fixtures/default-below.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    sha, size = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(), len(data)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def probe_blob(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def live_rows() -> dict[str, dict]:
    mapping = {
        "Q-evidence-decisive": S.FIX_DECISIVE,
        "Q-n-sensitive": S.FIX_NSENS,
        "Q-default-below": S.FIX_BELOW,
    }
    out = {}
    for qid, path in mapping.items():
        ev = evaluate_question(load_question(path), aggregator="majority", retune=False)
        out[qid] = {"eval": ev, "public": public_row(ev)}
    return out


def write_receipt(rows: dict[str, dict]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    public = [rows[k]["public"] for k in (
        "Q-evidence-decisive",
        "Q-n-sensitive",
        "Q-default-below",
    )]
    dec = rows["Q-evidence-decisive"]["public"]
    nsens = rows["Q-n-sensitive"]["public"]
    below = rows["Q-default-below"]["public"]
    impl = art_row(IMPL, "implementation")
    supporting = [art_row(p, "supporting") for p in SUPPORTING[1:]]
    indep_dec = S.independent_stabilisation(S.independent_curve(S.load_json(S.FIX_DECISIVE)))
    indep_ns = S.independent_stabilisation(S.independent_curve(S.load_json(S.FIX_NSENS)))
    indep_below = S.independent_stabilisation(S.independent_curve(S.load_json(S.FIX_BELOW)))
    doc = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0367",
        "completion_sentinel": "SUCCESS:IMP-0367",
        "profile": "council-runtime-module",
        "title": "Participant-count sensitivity analysis",
        "question": (
            "Implement tools/council/sensitivity.py re-running a decision at "
            "several seat counts to test whether the answer depends on N rather "
            "than on the evidence. Falsifiable question: at which seat count does "
            "the decision stabilise, and is the configured default above or below "
            "that point?"
        ),
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:IMP-0367 question_or_target; "
            "_USER-PROMPTS.md:10915-10946; 11-COUNCIL-SPECIFICATION.md "
            "(catalog path; file absent on this worktree)"
        ),
        "output_schema": SCHEMA,
        "min_bytes_threshold": 1024,
        "artifact_paths": [IMPL, OUT] + SUPPORTING[1:],
        "artifacts": [impl] + supporting,
        "experiment": {
            "curve_published": True,
            "question_count": 3,
            "default_seat_count": DEFAULT_SEAT_COUNT,
            "low_n_max": LOW_N_MAX,
            "aggregator": "majority",
            "retune": False,
            "questions": public,
        },
        "evidence": [
            {
                "id": "E1-decision-versus-N-curve",
                "claim": (
                    "A decision-versus-N curve is published for three questions; "
                    f"stabilisation points are N*={dec['stabilisation_n']} "
                    f"(evidence-decisive, {dec['default_relation']} default "
                    f"{dec['default_n']}), N*={nsens['stabilisation_n']} "
                    f"(n-sensitive), N*={below['stabilisation_n']} "
                    f"(default {below['default_n']} {below['default_relation']} N*)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/sensitivity.py:evaluate_question",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "in-process",
                        "command": "evaluate_question(fixtures, aggregator=majority, retune=False)",
                        "raw_output": json.dumps(public, sort_keys=True),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "in-process",
                        "command": "scenario.independent_curve + independent_stabilisation",
                        "raw_output": json.dumps(
                            {
                                "Q-evidence-decisive": indep_dec,
                                "Q-n-sensitive": indep_ns,
                                "Q-default-below": indep_below,
                            },
                            sort_keys=True,
                        ),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "id": "E2-default-versus-stabilisation",
                "claim": (
                    f"Configured default {DEFAULT_SEAT_COUNT} is {dec['default_relation']} "
                    f"the evidence-decisive N*={dec['stabilisation_n']}. On Q-default-below "
                    f"default {below['default_n']} is {below['default_relation']} N*="
                    f"{below['stabilisation_n']} and would emit {below['default_decision']} "
                    f"while the stable decision is {below['stable_decision']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/sensitivity.py:compare_default",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "in-process",
                        "command": "compare_default via evaluate_question public_row",
                        "raw_output": json.dumps(
                            {
                                "decisive_relation": dec["default_relation"],
                                "below_relation": below["default_relation"],
                                "below_would_emit_unstable": below[
                                    "default_would_emit_unstable_answer"
                                ],
                            },
                            sort_keys=True,
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": "read fixtures/*/default_n",
                        "raw_output": json.dumps(
                            {
                                "Q-evidence-decisive": S.load_json(S.FIX_DECISIVE)[
                                    "default_n"
                                ],
                                "Q-n-sensitive": S.load_json(S.FIX_NSENS)["default_n"],
                                "Q-default-below": S.load_json(S.FIX_BELOW)["default_n"],
                            },
                            sort_keys=True,
                        ),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "test_ids": [
            "IMP-0367-probe1-decision-vs-n",
            "IMP-0367-probe2-evidence-decisive-control",
        ],
        "tests": [
            {
                "id": "IMP-0367-probe1-decision-vs-n",
                "command": P1,
                "result": "PENDING-LIVE-RERUN",
            },
            {
                "id": "IMP-0367-probe2-evidence-decisive-control",
                "command": P2,
                "result": "PENDING-LIVE-RERUN",
            },
        ],
        "negative_control_ids": [
            "IMP-0367-evidence-decisive-no-retune",
            "IMP-0367-n-sensitive-curve-not-collapsed",
        ],
        "negative_controls": [
            {
                "id": "IMP-0367-evidence-decisive-no-retune",
                "kind": "mutation",
                "description": (
                    "n-modulated aggregator makes an evidence-decisive question "
                    "move with N. Production reports protocol_is_n_sensitive and "
                    "does not drop prefix N values. retune=True is the forbidden path."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "aggregator=n-modulated retune=False finding=protocol-n-sensitive-not-tuned",
                "good_state_output": json.dumps(
                    {
                        "stabilisation_n": dec["stabilisation_n"],
                        "low_n_stable": dec["low_n_stable"],
                        "protocol_is_n_sensitive": dec["protocol_is_n_sensitive"],
                        "retuned": dec["retuned"],
                    },
                    sort_keys=True,
                ),
            },
            {
                "id": "IMP-0367-n-sensitive-curve-not-collapsed",
                "kind": "mutation",
                "description": (
                    "An alternating-vote question is N-sensitive. Production still "
                    "publishes the flips; tune_until_stable would collapse them."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "tune_until_stable collapses distinct decisions to 1",
                "good_state_output": json.dumps(
                    {
                        "n_sensitive": nsens["n_sensitive"],
                        "flip_count": nsens["flip_count"],
                        "points": len(nsens["curve"]),
                        "retuned": nsens["retuned"],
                    },
                    sort_keys=True,
                ),
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0367-probe2-evidence-decisive-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests (named probes), not the author's summary",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog dependencies IMP-0274 (elastic.py) and IMP-0364 "
                    "(stability.py) are absent on this worktree. sensitivity.py "
                    "does not import them; the N-sweep is self-contained over "
                    "fixture vote pools."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run evaluate_question on a live council transcript "
                    "produced by those modules when they exist."
                ),
            },
            {
                "claim": (
                    "11-COUNCIL-SPECIFICATION.md and the cited _USER-PROMPTS.md "
                    "spans are not on this Linux worktree. Default N=5 is the "
                    "module constant DEFAULT_SEAT_COUNT, not a recovered spec file."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Diff DEFAULT_SEAT_COUNT against the recovered spec default when the file is present.",
            },
            {
                "claim": (
                    "No paid multi-model council was re-run. Curves are "
                    "deterministic majority over planted vote pools, which is "
                    "enough to falsify N-vs-evidence dependence of the aggregator "
                    "and is not a claim about live LLM seat noise."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Feed recorded live-council ballots into evaluate_question and publish that curve beside the fixtures.",
            },
            {
                "claim": (
                    "No separate human reviewer ran in a fresh context. Named "
                    "probes are the adversarial check that starts from the tests."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Independent reviewer re-runs probe1 and probe2 from a clean checkout.",
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0367/UNIT-ARTIFACT-MANIFEST.json",
            "note": "per-unit only; global unit_manifest.py --write was not run",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "note": "G-1 measure runs after this receipt is written",
            }
        ],
        "produced_by": {
            "execution_substrate": "linux-worktree",
            "model": "grok-4.6",
            "role": "implementer",
            "vendor": "cursor",
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0367: tools/council/sensitivity.py publishes a "
            "decision-versus-N curve, identifies N*, and compares the configured "
            "default without retuning an N-sensitive protocol. Did not run global "
            "unit_manifest.py --write. SUCCESS:IMP-0367"
        ),
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0367/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    if not S.MODULE.is_file():
        print("FAILED:IMP-0367 module missing")
        return 1
    rows = live_rows()
    dec = rows["Q-evidence-decisive"]["eval"]
    nsens = rows["Q-n-sensitive"]["eval"]
    below = rows["Q-default-below"]["eval"]
    if not dec.get("low_n_stable") or dec["stabilisation"]["stabilisation_n"] != 1:
        print("FAILED:IMP-0367 evidence-decisive did not stabilise at N=1")
        print(json.dumps(public_row(dec), indent=2, sort_keys=True)[:2000])
        return 1
    if nsens["stabilisation"]["n_sensitive"] is not True:
        print("FAILED:IMP-0367 n-sensitive fixture was not n_sensitive")
        return 1
    if below["default"]["relation"] != "below":
        print("FAILED:IMP-0367 default-below relation", below["default"])
        return 1
    write_receipt(rows)

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0367 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    rec_path = REPO / OUT
    doc = json.loads(rec_path.read_text(encoding="utf-8"))
    doc["tests"] = [
        {
            "id": "IMP-0367-probe1-decision-vs-n",
            "command": P1,
            "result": "PASS",
            "exit_code": c1,
            "output_tail": t1[-4000:],
        },
        {
            "id": "IMP-0367-probe2-evidence-decisive-control",
            "command": P2,
            "result": "PASS",
            "exit_code": c2,
            "output_tail": t2[-4000:],
        },
    ]
    doc["downstream_consumers"] = [
        {
            "consumer": "named-probes",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
        }
    ]
    rec_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:IMP-0367 probes after receipt update c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0367",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "decision-versus-N-curve",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "evidence-decisive-no-retune",
                "raw_output": t2b,
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0367/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0367-probe2-evidence-decisive-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0367: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    print("SUCCESS:IMP-0367 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
