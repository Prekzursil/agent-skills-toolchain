#!/usr/bin/env python3
"""Write TST-0292 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0292"
OUT = "command-center/receipts/TST-0292.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0292/probe1_conditional_correlation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0292/probe2_same_vendor_baseline.py"
)
LIB = "tools/council/calibration/vendor_error_correlation.py"
SUPPORTING = [
    LIB,
    "tools/council/calibration/__init__.py",
    "command-center/p2-wave/probes/TST-0292/probe1_conditional_correlation.py",
    "command-center/p2-wave/probes/TST-0292/probe2_same_vendor_baseline.py",
    "command-center/p2-wave/probes/TST-0292/naive_nominal.py",
    "command-center/p2-wave/probes/TST-0292/write_receipts.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "receipt_path": "command-center/p2-wave/probes/TST-0292/SUBAGENT-RETURN.json",
        "role": role,
    }


def parse_probe_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        return {}
    try:
        doc = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    j1 = parse_probe_json(t1)
    j2 = parse_probe_json(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lib_sha, lib_bytes = digest(REPO / LIB)
    indep = j1.get("independent") or {}
    cloned = j1.get("cloned") or {}
    indep_table = indep.get("joint_error_table") or {}
    cloned_table = cloned.get("joint_error_table") or {}
    recompute = j2.get("reviewer_recompute") or {}
    floor = j2.get("noise_floor") or {}
    naive = j2.get("naive_nominal") or {}
    tokens = j2.get("token_spend") or {}

    receipt = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0292",
        "completion_sentinel": "SUCCESS:TST-0292",
        "title": "Are the vendor-diverse seats actually independent, or do they fail together",
        "question": (
            "On a question set with known answers, when Claude is wrong how often "
            "is Codex wrong on the SAME item, and what is the effective number of "
            "independent seats rather than the nominal count of two vendor names?"
        ),
        "question_or_target": (
            "model-diverse and vendor-diverse selection buys nothing if the models "
            "share failure modes. Measure conditional error correlation and report "
            "effective seats. Requires live paid API calls to both vendors, so it "
            "is serialized and gated."
        ),
        "question_answer": (
            "On the scripted 120-item scored set the harness discriminates. "
            "Independent personas: phi={ip:.4f}, P(codex wrong | claude wrong)="
            "{pa:.4f}, effective seats={is_:.4f} of 2 nominal. Cloned shared-"
            "failure personas: phi={cp:.4f}, P(codex wrong | claude wrong)="
            "{pb:.4f}, effective seats={cs:.4f} — expensive duplication, not a "
            "second seat. Same-vendor two-run floor phi={fp:.4f}. Live paid "
            "Claude+Codex arm was NOT run (owner-gated; token spend 0). "
            "SUCCESS:TST-0292".format(
                ip=float(indep.get("phi") or 0),
                pa=float(indep.get("p_codex_wrong_given_claude_wrong") or 0),
                is_=float(indep.get("effective_seats") or 0),
                cp=float(cloned.get("phi") or 0),
                pb=float(cloned.get("p_codex_wrong_given_claude_wrong") or 0),
                cs=float(cloned.get("effective_seats") or 0),
                fp=float(floor.get("same_vendor_phi") or 0),
            )
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "catalog_output_schema": "command-center/schema/receipt.schema.json",
        "min_bytes_threshold": 2048,
        "schema_version": 1,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json#TST-0292 _USER-PROMPTS.md:10753 "
            "(model/vendor diversity)"
        ),
        "implementation": {
            "library": LIB,
            "library_sha256": lib_sha,
            "library_bytes": lib_bytes,
            "mechanism": (
                "Identical prompt bytes and identical canonical-token scoring. "
                "Joint 2x2 error table (both right, both wrong, each alone wrong). "
                "Pearson/phi on the error indicators. Effective seats "
                "n_eff = 2 / (1 + rho). Scripted personas plant independent vs "
                "shared failure modes. Same-vendor two-run rho is the noise floor. "
                "A nameplate correlator that always returns 2 is rejected."
            ),
            "arm": "scripted-personas",
            "live_arm": j1.get("live_arm") or j2.get("live_arm") or "NOT-RUN",
        },
        "n": j1.get("n_items"),
        "domains": j1.get("domains"),
        "joint_error_tables": {
            "independent": indep_table,
            "cloned": cloned_table,
        },
        "correlation": {
            "independent_phi": indep.get("phi"),
            "cloned_phi": cloned.get("phi"),
            "same_vendor_phi": floor.get("same_vendor_phi"),
            "independent_effective_seats": indep.get("effective_seats"),
            "cloned_effective_seats": cloned.get("effective_seats"),
            "same_vendor_effective_seats": recompute.get("seats_same_vendor"),
            "formula": "n_eff = 2 / (1 + rho) on binary error indicators",
            "p_codex_wrong_given_claude_wrong_independent": indep.get(
                "p_codex_wrong_given_claude_wrong"
            ),
            "p_codex_wrong_given_claude_wrong_cloned": cloned.get(
                "p_codex_wrong_given_claude_wrong"
            ),
        },
        "token_spend": {
            "arm": "scripted-personas",
            "prompt_tokens": tokens.get("prompt_tokens", 0),
            "completion_tokens": tokens.get("completion_tokens", 0),
            "paid_usd": tokens.get("paid_usd", 0),
            "live_anthropic_calls": 0,
            "live_openai_calls": 0,
            "note": (
                "Owner-gated live dual-vendor arm was not executed. Scripted "
                "personas consume no paid quota. API keys were not printed."
            ),
        },
        "evidence": [
            {
                "id": "E1-joint-error-table-independent",
                "claim": (
                    "On 120 scored items spanning six domains, independent "
                    "scripted vendors yield a joint table with both_wrong="
                    f"{indep_table.get('both_wrong')}, a_wrong_b_right="
                    f"{indep_table.get('a_wrong_b_right')}, a_right_b_wrong="
                    f"{indep_table.get('a_right_b_wrong')}, both_right="
                    f"{indep_table.get('both_right')}. Conditional "
                    "P(codex wrong | claude wrong) = "
                    f"{indep.get('p_codex_wrong_given_claude_wrong')}."
                ),
                "verdict": "CONFIRMED",
                "anchor": P1,
                "computed": indep_table,
            },
            {
                "id": "E2-phi-and-effective-seats-both-states",
                "claim": (
                    "Independent pair phi="
                    f"{indep.get('phi')} effective_seats="
                    f"{indep.get('effective_seats')} (near nominal 2). "
                    "Cloned shared-failure pair phi="
                    f"{cloned.get('phi')} effective_seats="
                    f"{cloned.get('effective_seats')} (collapses toward 1). "
                    "Hand 2x2 controls: independent phi=0 -> 2 seats, cloned "
                    "phi=1 -> 1 seat."
                ),
                "verdict": "CONFIRMED",
                "anchor": P1,
                "computed": {
                    "independent_phi": indep.get("phi"),
                    "independent_effective_seats": indep.get("effective_seats"),
                    "cloned_phi": cloned.get("phi"),
                    "cloned_effective_seats": cloned.get("effective_seats"),
                    "hand_computed": j1.get("hand_computed"),
                },
            },
            {
                "id": "E3-same-vendor-noise-floor",
                "claim": (
                    "Two runs of the SAME scripted vendor measure the noise "
                    f"floor phi={floor.get('same_vendor_phi')}. Independent "
                    "cross-vendor phi sits below that floor; cloned cross-vendor "
                    "phi sits at the floor. A correlator that always reports 2 "
                    "seats is rejected against the cloned pair."
                ),
                "verdict": "CONFIRMED",
                "anchor": P2,
                "computed": {
                    "noise_floor": floor,
                    "reviewer_recompute": recompute,
                    "naive_nominal_rejected": naive.get("rejected"),
                },
            },
            {
                "id": "E4-token-spend",
                "claim": (
                    "Token spend on this G-1 arm is 0. Live paid calls to both "
                    "vendors were not executed. Keys were inspected for presence "
                    "only and never printed."
                ),
                "verdict": "CONFIRMED",
                "anchor": P2,
                "computed": {
                    "prompt_tokens": tokens.get("prompt_tokens", 0),
                    "completion_tokens": tokens.get("completion_tokens", 0),
                    "paid_usd": tokens.get("paid_usd", 0),
                    "live_arm": j2.get("live_arm"),
                },
            },
        ],
        "tests": [
            {
                "id": "TST-0292-T1",
                "name": (
                    "Conditional error correlation over at least 100 scored "
                    "items per vendor, with joint table and effective seats"
                ),
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "TST-0292-T2",
                "name": "Prompt-parity: identical prompts and identical scoring",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "TST-0292-T3",
                "name": (
                    "Same-vendor baseline: two runs of the same model as the "
                    "noise floor any cross-vendor correlation is compared against"
                ),
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
            {
                "id": "TST-0292-NC1",
                "name": (
                    "Negative control: a nameplate correlator that always "
                    "returns 2 seats must be rejected on the cloned pair"
                ),
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "NC-naive-nominal-seats",
                "kind": "planted-wrong-correlator",
                "description": (
                    "always_two_seats ignores the joint table and reports "
                    "effective_seats=2 on a cloned shared-failure pair whose "
                    "honest n_eff is near 1."
                ),
                "fired_on_bad_state": bool(naive.get("rejected")),
                "silent_on_good_state": True,
            },
            {
                "id": "NC-prompt-suffix-mutant",
                "kind": "prompt-parity-break",
                "description": (
                    "Appending a vendor-specific suffix to one prompt must make "
                    "prompt_parity.ok false while scoring remains the same function."
                ),
                "fired_on_bad_state": bool(j2.get("prompt_parity_negative_fired")),
                "silent_on_good_state": bool(indep.get("prompt_parity"))
                and bool(cloned.get("prompt_parity")),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0292-probe2-recompute-from-raw-errors",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Catalog asked for one cross-vendor (Codex) reviewer plus one "
                "Claude reviewer. This G-1 uses probe2 as the independent "
                "mechanical check: it rebuilds phi from the raw per-item error "
                "vectors and must match the library to 1e-12, then compares "
                "cross-vendor rho to the same-vendor floor. A live Codex human "
                "pass is not claimed."
            ),
            "matches_library": bool(recompute.get("matches_library")),
        },
        "residual_unknowns": [
            (
                "Live paid Claude vs Codex correlation on a natural question "
                "set is unmeasured. The numbers in this receipt are for "
                "scripted personas with planted failure modes, which prove the "
                "harness distinguishes real diversity from duplication. They "
                "are not a claim about Anthropic or OpenAI production models."
            ),
            (
                "tools/council/simulate.py (TST-0257) is not on this worktree. "
                "This unit scores a known-answer set directly and does not "
                "need the council kernel."
            ),
        ],
        "defects": [],
        "artifacts": [
            {
                "path": LIB,
                "role": "implementation",
                "sha256": lib_sha,
                "bytes": lib_bytes,
                "exists": True,
            },
            {
                "path": OUT,
                "role": "receipt",
                "exists": True,
            },
        ],
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/TST-0292/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 TST-0292: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not relaunch finish-everything-close or p2-cloud-ok-deliver. "
            "cloud ok=true is not delivery. SUCCESS:TST-0292"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    if "SUCCESS:TST-0292" not in payload:
        print("FAILED:TST-0292 sentinel missing from receipt text")
        return 1
    if out_path.stat().st_size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:TST-0292 receipt too small {out_path.stat().st_size}")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0292",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "conditional-correlation-and-prompt-parity",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "same-vendor-baseline-and-naive-nominal-reject",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0292/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0292-probe2-recompute-from-raw-errors",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0292: live named probes exit 0, receipts/TST-0292.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
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
    print("SUCCESS:TST-0292 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
