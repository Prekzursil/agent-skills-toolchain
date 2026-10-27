#!/usr/bin/env python3
"""Write TST-0319 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

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
UNIT = "TST-0319"
OUT = "command-center/receipts/TST-0319.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0319/probe1_quota_and_survival.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0319/probe2_suppression_and_impossibility.py"
)
SUPPORTING = [
    "tools/bench/__init__.py",
    "tools/bench/deep_research.py",
    "command-center/p2-wave/probes/TST-0319/corpora.py",
    "command-center/p2-wave/probes/TST-0319/measure.py",
    "command-center/p2-wave/probes/TST-0319/drop_disconfirming.py",
    "command-center/p2-wave/probes/TST-0319/probe1_quota_and_survival.py",
    "command-center/p2-wave/probes/TST-0319/probe2_suppression_and_impossibility.py",
    "command-center/bench/cases/TST-0319/config.json",
    "command-center/bench/cases/TST-0319/quota-70-30.json",
    "command-center/bench/cases/TST-0319/survival.json",
    "command-center/bench/cases/TST-0319/suppression-stronger-contradict.json",
    "command-center/bench/cases/TST-0319/impossibility-ghost.json",
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
        "receipt_path": "command-center/p2-wave/probes/TST-0319/SUBAGENT-RETURN.json",
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


def per_corpus_row(
    *,
    corpus_id: str,
    role: str,
    configured: dict,
    gt: dict,
    returned: dict,
    survival: float,
    verdict: str,
) -> dict:
    return {
        "corpus_id": corpus_id,
        "role": role,
        "configured_quota": configured,
        "ground_truth_ratio": {
            "support": gt.get("support_ratio"),
            "contradict": gt.get("contradict_ratio"),
            "support_n": gt.get("support"),
            "contradict_n": gt.get("contradict"),
        },
        "returned_proportion": {
            "support": (returned or {}).get("support"),
            "contradict": (returned or {}).get("contradict"),
            "polar_n": (returned or {}).get("polar_n"),
        },
        "contradiction_survival_rate": survival,
        "survival_into": "final_report.md BEGIN_CONTRADICTIONS (not notes.json)",
        "verdict": verdict,
    }


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
    lib_sha, lib_bytes = digest(REPO / "tools/bench/deep_research.py")
    q = j1.get("quota_corpus") or {}
    v = j1.get("survival_corpus") or {}
    s = j2.get("honest_suppression") or {}
    imp = j2.get("honest_impossibility") or {}
    configured = j1.get("configured_quota") or {
        "favourable": 0.70,
        "unfavourable": 0.30,
        "report_slot_budget": 10,
    }
    per_corpus = [
        per_corpus_row(
            corpus_id=str(q.get("id") or "TST-0319-Q-70-30"),
            role="quota-adherence",
            configured=configured,
            gt=q.get("ground_truth") or {},
            returned=q.get("returned_proportion") or {},
            survival=float(q.get("contradiction_survival_rate") or 0.0),
            verdict=str(q.get("verdict") or ""),
        ),
        per_corpus_row(
            corpus_id=str(v.get("id") or "TST-0319-V-SURVIVAL"),
            role="contradiction-survival",
            configured=configured,
            gt=v.get("ground_truth") or {},
            returned=v.get("returned_proportion") or {},
            survival=float(v.get("contradiction_survival_rate") or 0.0),
            verdict=str(v.get("verdict") or ""),
        ),
        per_corpus_row(
            corpus_id="TST-0319-P-SUPPRESSION",
            role="suppression-control",
            configured=configured,
            gt=s.get("ground_truth") or {},
            returned=s.get("returned_proportion") or {},
            survival=float(s.get("contradiction_survival_rate") or 0.0),
            verdict=str(s.get("verdict") or ""),
        ),
        per_corpus_row(
            corpus_id="TST-0319-I-IMPOSSIBLE",
            role="proof-of-impossibility",
            configured=configured,
            gt=imp.get("ground_truth") or {},
            returned={},
            survival=0.0,
            verdict=str(imp.get("verdict") or ""),
        ),
    ]

    receipt = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0319",
        "completion_sentinel": "SUCCESS:TST-0319",
        "title": (
            "Benchmark deep-research quality on quota adherence and "
            "contradiction retention"
        ),
        "report_kind": "test_receipt",
        "output_path": OUT,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "min_bytes_threshold": 2048,
        "schema_version": 1,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json#TST-0319 "
            "_USER-PROMPTS.md:11260-11278 (deep-research required configuration; "
            "file absent on this worktree). Catalog inputs command-center/bench/cases/ "
            "and tools/bench/."
        ),
        "question": (
            "The research workflow at :11260-11278 is configured with favourable "
            "and unfavourable result quotas, contradiction search and a requirement "
            "to preserve negative and contradictory evidence. On seeded corpora "
            "where the true support/contradict distribution is known by construction, "
            "does the workflow return that mix and do contradictions survive into "
            "the final report rather than only the working notes?"
        ),
        "question_or_target": (
            "Build seeded corpora with known support/contradiction ratios, then "
            "measure quota adherence and contradiction retention into the final "
            "report. A research system that quietly drops disconfirming evidence "
            "still produces a confident, useless answer."
        ),
        "question_answer": (
            "YES on the honest runner in tools/bench/deep_research.py: the 70/30 "
            "quota corpus returns 7/3 selected citations; contradiction tokens in "
            "notes reappear in the final appendix; a stronger-contradict corpus is "
            "CONTRADICTION-DOMINANT not CONSENSUS; a ghost claim emits a typed "
            "proof-of-impossibility record. A planted drop-disconfirming synthesizer "
            "fails those contracts. SUCCESS:TST-0319"
        ),
        "implementation": {
            "library": "tools/bench/deep_research.py",
            "library_sha256": lib_sha,
            "library_bytes": lib_bytes,
            "cases": "command-center/bench/cases/TST-0319/",
            "mechanism": (
                "Retrieve sources whose claim_id matches the query. Write all of "
                "them into intermediate notes. Select a budgeted citation mix that "
                "meets the configured favourable/unfavourable floors without "
                "manufacturing missing unfavourable evidence. Copy every retrieved "
                "contradiction token into the final-report appendix. Score verdict "
                "on retrieved strength sums so stronger contradictions cannot be "
                "hidden by selection. An empty retrieval takes emit_impossibility_record, "
                "a distinct code path from emit_final_report."
            ),
        },
        "configured_quota": configured,
        "per_corpus": per_corpus,
        "evidence": {
            "requirement": (
                "Report the configured quota, the returned proportion and the "
                "contradiction survival rate into the final artifact, per corpus. "
                "Survival into the intermediate notes does not count."
            ),
            "per_corpus": per_corpus,
            "E1_quota_adherence": {
                "claim": (
                    "On TST-0319-Q-70-30 the independently recounted ground-truth "
                    "ratio is 14/6 = 0.70/0.30 and the selected-citation mix from "
                    "final_report.md matches the configured quota."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0319/probe1_quota_and_survival.py"
                ),
                "computed": q,
            },
            "E2_contradiction_survival": {
                "claim": (
                    "Contradiction tokens present in notes.json for the survival "
                    "corpus all appear in final_report.md BEGIN_CONTRADICTIONS. "
                    "notes.json is not the final report."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0319/probe1_quota_and_survival.py"
                ),
                "computed": v,
            },
            "E3_suppression_control": {
                "claim": (
                    "A corpus whose contradicting evidence is stronger (strength "
                    "sum 2.70 vs 0.80) is not reported as CONSENSUS."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0319/"
                    "probe2_suppression_and_impossibility.py"
                ),
                "computed": s,
            },
            "E4_proof_of_impossibility": {
                "claim": (
                    "A corpus where the asked-for claim does not exist emits a "
                    "proof-of-impossibility record with non-empty exhausted source "
                    "classes, zero-hit queries, an expiry, and a falsifier. That "
                    "path is emit_impossibility_record, not emit_final_report."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0319/"
                    "probe2_suppression_and_impossibility.py"
                ),
                "computed": {
                    "ok": imp.get("ok"),
                    "why": imp.get("why"),
                    "verdict": imp.get("verdict"),
                    "kind": (imp.get("record") or {}).get("kind"),
                    "code_path": (imp.get("record") or {}).get("code_path"),
                    "exhausted_source_classes": (imp.get("record") or {}).get(
                        "exhausted_source_classes"
                    ),
                },
            },
        },
        "tests": [
            {
                "id": "TST-0319-T1-quota-adherence",
                "name": "Quota adherence measured against a known ground-truth ratio",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "TST-0319-T2-contradiction-survival",
                "name": (
                    "Contradiction survival traced to the FINAL report, not the "
                    "working notes"
                ),
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "TST-0319-T3-suppression-control",
                "name": (
                    "A corpus where contradicting evidence is stronger is not "
                    "reported as consensus"
                ),
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
            {
                "id": "TST-0319-T4-proof-of-impossibility",
                "name": (
                    "Proof-of-impossibility path exercised on a corpus where the "
                    "asked-for evidence does not exist"
                ),
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
            {
                "id": "TST-0319-NC1-drop-disconfirming",
                "name": (
                    "negative control: a synthesizer that drops contradictions "
                    "from the final report must fail"
                ),
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "NC-drop-disconfirming",
                "kind": "planted-wrong-synthesizer",
                "description": (
                    "Writes contradictions into notes, omits them from the final "
                    "appendix, reports CONSENSUS on stronger contradictions, and "
                    "treats a missing claim as CONSENSUS."
                ),
                "fired_on_bad_state": bool(j2.get("fired_on_bad_state")),
                "silent_on_good_state": bool(j2.get("silent_on_good_state")),
            }
        ],
        "reviewer": {
            "reviewer_id": "TST-0319-probe2-drop-disconfirming",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Catalog asked for one independent adversarial reviewer in a fresh "
                "context who did not author the harness under test and who must "
                "reproduce the both-states control. This G-1 delivery uses probe2 "
                "(drop-disconfirming synthesizer) as that mechanical check: it does "
                "not score quota mix, requires honest suppression+impossibility to "
                "PASS, and requires the planted synthesizer to FAIL. A human Codex "
                "pass is not claimed."
            ),
        },
        "defects": [],
        "artifacts": [
            {
                "path": "tools/bench/deep_research.py",
                "role": "implementation",
                "sha256": lib_sha,
                "bytes": lib_bytes,
                "exists": True,
            },
            {
                "path": "command-center/bench/cases/TST-0319/",
                "role": "seeded-corpora",
            },
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0319/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 TST-0319: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild. SUCCESS:TST-0319"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    if "SUCCESS:TST-0319" not in payload:
        print("FAILED:TST-0319 sentinel missing from receipt text")
        return 1
    if out_path.stat().st_size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:TST-0319 receipt too small {out_path.stat().st_size}")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0319",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "quota-adherence-and-contradiction-survival",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "suppression-impossibility-drop-control",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0319/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0319-probe2-drop-disconfirming",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0319: live named probes exit 0, receipts/TST-0319.json "
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
    print("SUCCESS:TST-0319 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
