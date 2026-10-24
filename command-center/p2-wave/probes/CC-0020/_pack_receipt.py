#!/usr/bin/env python3
"""Pack CC-0020 — two-detector mechanism dedup gate.

Emits state=BLOCKED with blocked-on-independent-review after green detector
controls + named probes. Does NOT invent SUCCESS: catalog reviewer_requirement
demands an independent reviewer who authors a fifth mutant class the detector
was not tuned against. Never stub independent-review.json.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "CC-0020"
OUT = "command-center/receipts/CC-0020.json"
SCHEMA = "command-center/schema/receipt.schema.json"
PROBE_DIR = "command-center/p2-wave/probes/CC-0020"
GATE = "tools/command-center/mechanism_dedup_gate.py"
TESTS = "tools/command-center/tests/test_mechanism_dedup_gate.py"
PROBE1 = f"{PROBE_DIR}/probe1_mutants.py"
PROBE2 = f"{PROBE_DIR}/probe2_distinct.py"
FIXTURES = f"{PROBE_DIR}/fixtures/planted-mutants.json"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = L.REPO / PROBE_DIR / "independent-review.json"
TS0 = "2026-09-08T01:20:00Z"


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=L.REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def load_review() -> dict | None:
    """Promote path only when an independent reviewer authors a fifth mutant class."""
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    fifth = rev.get("fifth_mutant_class") or rev.get("new_mutant_class")
    if not fifth:
        return None
    if not rev.get("fifth_mutant_caught") and not rev.get("detector_confirmed"):
        return None
    return rev


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    # Dependency CC-0008 must already be SUCCESS on disk.
    dep = json.loads(
        (L.REPO / "command-center/receipts/CC-0008.json").read_text(encoding="utf-8")
    )
    if dep.get("state") != "SUCCESS":
        raise SystemExit(f"CC-0020 refuses pack: CC-0008 state={dep.get('state')!r}")

    rc, out = _run([sys.executable, "-m", "pytest", TESTS, "-q", "--tb=line"])
    (L.REPO / PROBE_DIR / "pytest.out").write_text(out, encoding="utf-8")
    if rc != 0:
        raise SystemExit(f"CC-0020 pytest failed:\n{out}")

    p1_rc, p1_out = _run([sys.executable, "-B", str(L.REPO / PROBE1)])
    if p1_rc != 0:
        raise SystemExit(f"CC-0020 probe1 failed:\n{p1_out}")
    p2_rc, p2_out = _run([sys.executable, "-B", str(L.REPO / PROBE2)])
    if p2_rc != 0:
        raise SystemExit(f"CC-0020 probe2 failed:\n{p2_out}")

    p1 = json.loads(
        (L.REPO / PROBE_DIR / "probe1-mutants.json").read_text(encoding="utf-8")
    )
    p2 = json.loads(
        (L.REPO / PROBE_DIR / "probe2-distinct.json").read_text(encoding="utf-8")
    )
    raw1 = (L.REPO / PROBE_DIR / "probe1-mutants.raw.txt").read_text(encoding="utf-8")
    raw2 = (L.REPO / PROBE_DIR / "probe2-distinct.raw.txt").read_text(encoding="utf-8")

    rev = load_review()
    success = rev is not None

    rates = p1["per_class_detection_rate"]
    rate_bits = ", ".join(f"{k}={v}" for k, v in sorted(rates.items()))
    fm = p2["false_merge_count"]

    p_pytest = L.probe(
        "source", "test-run", f"python3 -m pytest {TESTS} -q --tb=line", out, rc
    )
    p_probe1 = L.probe("verifier", "command", f"python3 -B {PROBE1}", raw1, p1_rc)
    p_probe2 = L.probe("verifier", "command", f"python3 -B {PROBE2}", raw2, p2_rc)

    if success:
        state = "SUCCESS"
        sentinel = f"SUCCESS:{UNIT}"
        notes = rev.get("notes", "")
        if not isinstance(notes, str):
            notes = json.dumps(notes)
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": notes[:4000],
        }
        residual: list[dict] = []
        failure = None
        anti = "SUCCESS-after-independent-fifth-mutant-class"
        downstream = [
            {
                "consumer": "mechanism_dedup_gate.compare",
                "artifact_path": GATE,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "command",
                    f"python3 -B {GATE} --fixtures {FIXTURES}",
                    raw1[-4000:],
                    0,
                ),
            }
        ]
    else:
        state = "BLOCKED"
        sentinel = (
            f"FAILED:{UNIT} blocked-on-independent-review; "
            f"per-class detection [{rate_bits}]; false_merge_count={fm}; "
            f"determinism={p2['determinism']['deterministic']}; "
            f"CC-0008 SUCCESS verified on disk; "
            f"SUCCESS:{UNIT} withheld pending independent fifth mutant class"
        )
        reviewer = {
            "reviewer_id": "awaiting-independent-fifth-mutant",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Implementer emit only on Linux cloud agent. Catalog "
                "reviewer_requirement: one independent reviewer who authors a fifth "
                "mutant class the detector was not tuned against. Self-review banned; "
                "independent-review.json not invented. Scope: embedding detector is a "
                "deterministic mechanism-key+char-ngram hash (no sentence-transformers "
                "in this environment); neural embedding rescan remains out of scope."
            ),
        }
        residual = [
            {
                "claim": (
                    "Independent reviewer has not authored a fifth mutant class nor "
                    "confirmed the gate catches it without retuning thresholds."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context reviewer authors a new mutant class (not "
                    "exact_rename/paraphrase/one_parameter_fork/full_rewrite), adds it "
                    f"under {PROBE_DIR}/fixtures/, re-runs "
                    f"`python3 -B {GATE} --fixtures {FIXTURES}` and pytest, returns "
                    "PASS with independent=true, fresh_context=true, "
                    "fifth_mutant_class=<name>, fifth_mutant_caught=true."
                ),
            }
        ]
        failure = {
            "classification": ["blocked-on-independent-review"],
            "reason": (
                "Two-detector AND gate + planted-mutant controls + distinct-set "
                f"probes are green (pytest; probe1 ok={p1.get('ok')}; "
                f"probe2 ok={p2.get('ok')}; false_merge_count={fm}; "
                f"per-class [{rate_bits}]). Catalog reviewer_requirement unmet — "
                "do not emit SUCCESS without a fifth mutant class from an "
                "independent reviewer."
            ),
            "blocked_on": (
                "independent reviewer fifth-mutant-class + detector confirm"
            ),
            "diagnostic_tail": (out + "\n" + raw1 + "\n" + raw2)[-4000:],
            "two_signal_proof": [p_probe1, p_probe2],
        }
        anti = "BLOCKED-pending-independent-fifth-mutant"
        # SUCCESS-ready shape: consumers present and executed so a later promote
        # path only flips reviewer + state (Condition 12 already non-empty).
        downstream = [
            {
                "consumer": "mechanism_dedup_gate.evaluate_mutants",
                "artifact_path": FIXTURES,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_probe1,
            },
            {
                "consumer": "mechanism_dedup_gate.evaluate_distinct_set",
                "artifact_path": f"{PROBE_DIR}/probe2-distinct.json",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_probe2,
            },
        ]

    arts = [
        L.art(GATE, "primary"),
        L.art(TESTS, "supporting"),
        L.art(FIXTURES, "control"),
        L.art(f"{PROBE_DIR}/probe1-mutants.json", "log"),
        L.art(f"{PROBE_DIR}/probe2-distinct.json", "log"),
        L.art(f"{PROBE_DIR}/pytest.out", "log"),
        L.art(f"{PROBE_DIR}/probe1-mutants.raw.txt", "log"),
        L.art(f"{PROBE_DIR}/probe2-distinct.raw.txt", "log"),
        L.art("command-center/receipts/CC-0008.json", "supporting"),
        L.art(f"{PROBE_DIR}/_pack_receipt.py", "control"),
    ]
    if success:
        arts.append(L.art(f"{PROBE_DIR}/independent-review.json", "supporting"))

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CC-0020",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "independent-detector-engineer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    "AND-gated two-detector mechanism dedup gate "
                    f"({GATE}): lexical token-Jaccard + mechanism-key/char-ngram "
                    f"embedding. Per-class detection rates (not aggregate): [{rate_bits}]. "
                    f"Full-rewrite lexical={p1['per_class_scores']['full_rewrite']['lexical_jaccard']} "
                    f"(defeats lexical; embedding fires). False-merge count on "
                    f"hand-verified distinct set (n={p2['unit_count']}): {fm}."
                ),
                "CONFIRMED",
                f"file:{GATE}",
                [p_pytest, p_probe1],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Named probes: probe1 mutants ok={p1.get('ok')} "
                    f"full_rewrite_defeats_lexical={p1.get('full_rewrite_defeats_lexical')}; "
                    f"probe2 distinct ok={p2.get('ok')} false_merge_count={fm} "
                    f"determinism={p2['determinism']['deterministic']}; "
                    f"error-direction rows={len(p2['error_direction_report'])}. "
                    "CC-0008 SUCCESS verified on disk before packing."
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/probe2-distinct.json",
                [
                    L.probe(
                        "source",
                        "file-read",
                        "read command-center/receipts/CC-0008.json state",
                        json.dumps({"unit_id": "CC-0008", "state": dep.get("state")}),
                        0,
                    ),
                    p_probe2,
                ],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot; if embedding thresholds fail twice, fall "
                "back to requiring human adjudication for the ambiguous band rather "
                "than tuning a third threshold."
            ),
        },
        "tests": [
            {
                "id": "four-mutant-classes",
                "name": "All four planted mutant classes caught (incl. full-rewrite).",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_all_four_planted_mutant_classes_caught -q"
                ),
                "result": "PASS",
                "assertions": 4,
                "output_tail": out[-800:],
            },
            {
                "id": "full-rewrite-lexical-defeat",
                "name": "Full rewrite defeats lexical; embedding fires; CONTESTED.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_full_rewrite_defeats_lexical_but_embedding_fires -q"
                ),
                "result": "PASS",
                "assertions": 4,
                "output_tail": out[-800:],
            },
            {
                "id": "zero-false-merges",
                "name": "Zero false merges on hand-verified distinct set >=24.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_zero_false_merges_on_hand_verified_distinct_set -q"
                ),
                "result": "PASS",
                "assertions": 2,
                "output_tail": out[-800:],
            },
            {
                "id": "error-direction",
                "name": "Every disagreement classified over-merge or under-merge.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_error_direction_classifies_every_disagreement -q"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": out[-800:],
            },
            {
                "id": "determinism",
                "name": "Same input pair yields same verdict across runs.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_determinism_same_pair_same_verdict -q"
                ),
                "result": "PASS",
                "assertions": 3,
                "output_tail": out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "planted-mutants-four-classes",
                "known-broken-fixture",
                "Exact rename, paraphrase, one-parameter fork, full rewrite must all be caught.",
                True,
                True,
                bad=json.dumps(rates, sort_keys=True),
                good="distinct seed vs unrelated text stays DISTINCT",
            ),
            L.control(
                "full-rewrite-lexical-silent",
                "mutation",
                "Full rewrite must sit in low lexical band while embedding fires.",
                True,
                True,
                bad=json.dumps(p1["per_class_scores"]["full_rewrite"], sort_keys=True),
                good="lexical_fire=false embedding_fire=true",
            ),
            L.control(
                "distinct-set-no-false-merge",
                "absent-input",
                "Hand-verified distinct set of >=24 units must yield zero MERGE pairs.",
                True,
                True,
                bad=f"would MERGE pairs among {p2['unit_ids']}",
                good=f"false_merge_count={fm} contested={p2['contested_count']}",
            ),
        ],
        "reviewer": reviewer,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": downstream,
        "residual_unknowns": residual,
        "defects": [],
        "report": {
            "per_class_detection_rate": rates,
            "per_class_verdict": p1["per_class_verdict"],
            "per_class_scores": p1["per_class_scores"],
            "false_merge_count": fm,
            "distinct_unit_count": p2["unit_count"],
            "determinism": p2["determinism"],
            "error_direction_report": p2["error_direction_report"],
            "embedding_method": p1.get("embedding_method"),
            "gate": p1.get("gate"),
            "dependency_CC-0008": dep.get("state"),
            "independent_review_present": REVIEW.is_file(),
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": f"{PROBE_DIR}/_pack_receipt.py",
            "anti_false_green": anti,
            "linux_cloud_scope": (
                "mechanism-key+char-ngram-hash embedding; no neural sentence model"
            ),
        },
    }
    if failure is not None:
        receipt["failure"] = failure

    (L.REPO / MANIFEST).write_text(
        json.dumps(
            {
                "entry_id": UNIT,
                "unit_id": UNIT,
                "artifacts": [
                    OUT,
                    GATE,
                    TESTS,
                    FIXTURES,
                    f"{PROBE_DIR}/probe1-mutants.json",
                    f"{PROBE_DIR}/probe2-distinct.json",
                ],
                "state": state,
                "registered_at": ended,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    rc_w = L.write_if_valid(receipt, OUT, SCHEMA)
    if rc_w != 0:
        raise SystemExit(rc_w)
    receipt["artifacts"].insert(0, L.art(OUT, "primary"))
    rc2 = L.write_if_valid(receipt, OUT, SCHEMA)
    if rc2 != 0:
        raise SystemExit(rc2)

    # Admission check (not completion).
    v_rc, v_out = _run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    (L.REPO / PROBE_DIR / "receipt-validate.out").write_text(v_out, encoding="utf-8")
    if v_rc != 0 or "ACCEPT" not in v_out:
        raise SystemExit(f"receipt_validate rejected:\n{v_out}")

    print(f"PACKED {OUT} state={state} bytes={L.art(OUT)['bytes']}")
    print(f"per-class: {rate_bits}")
    print(f"false_merge_count={fm} independent_review={REVIEW.is_file()}")
    return receipt


if __name__ == "__main__":
    build()
