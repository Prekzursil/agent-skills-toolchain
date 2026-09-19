#!/usr/bin/env python3
"""Pack IMP-0456 — catalog slice merge contiguity as honest BLOCKED receipt.

Catalog reviewer_requirement: independent-claude-reviewer recounts each slice
independently from the files on disk. Never invent SUCCESS. Never invent
independent-review.json.

Live tree measured shortfall (2007 vs floor 2048) with index gaps — contiguous
gate refuses honestly. Planted dup/gap/clean controls must be green.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "IMP-0456"
OUT = "command-center/receipts/IMP-0456.json"
SCHEMA = "command-center/schema/receipt.schema.json"
ALSO = ["command-center/schema/receipt.schema.json"]
PROBE_DIR = "command-center/p2-wave/probes/IMP-0456"
MERGER = "tools/command-center/catalog_slice_merge.py"
TESTS = "tools/command-center/tests/test_catalog_merge_contiguous.py"
LEGACY_TESTS = "tools/command-center/tests/test_catalog_slice_merge.py"
MEASURE = f"{PROBE_DIR}/measure_merge.py"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
REPORT = f"{PROBE_DIR}/merge-report.json"
REVIEW = L.REPO / PROBE_DIR / "independent-review.json"
DEP = "command-center/receipts/IMP-0436.json"
TS0 = "2026-09-08T02:40:00Z"


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
    """Promote only when independent recount review is present and PASS."""
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
    # Must claim a per-slice recount from disk.
    if not rev.get("recounted_each_slice_from_disk"):
        return None
    return rev


def verify_dep() -> dict:
    path = L.REPO / DEP
    if not path.is_file():
        raise SystemExit(f"IMP-0456 dependency missing: {DEP}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("state") != "SUCCESS":
        raise SystemExit(
            f"IMP-0456 dependency IMP-0436 state={doc.get('state')!r} "
            f"(required SUCCESS) sentinel={doc.get('sentinel')!r}"
        )
    return {
        "unit_id": "IMP-0436",
        "state": doc["state"],
        "sentinel": doc.get("sentinel"),
        "path": DEP,
    }


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    dep = verify_dep()

    # Never invent independent-review.json.
    if REVIEW.is_file() and load_review() is None:
        # Present but invalid — still do not treat as SUCCESS path unless PASS.
        pass

    rc, out = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            TESTS,
            LEGACY_TESTS,
            "-q",
            "--tb=line",
        ]
    )
    (L.REPO / PROBE_DIR / "pytest.out").write_text(out, encoding="utf-8")
    if rc != 0:
        raise SystemExit(f"IMP-0456 pytest failed:\n{out}")

    m_rc, m_out = _run([sys.executable, "-B", str(L.REPO / MEASURE)])
    (L.REPO / PROBE_DIR / "measure.out").write_text(m_out, encoding="utf-8")
    if m_rc != 0:
        raise SystemExit(f"IMP-0456 measure_merge failed:\n{m_out}")

    report = json.loads((L.REPO / REPORT).read_text(encoding="utf-8"))
    if report.get("exact_question", {}).get("answer") is True:
        # Live contiguous green would be surprising; still require independent
        # recount before SUCCESS. Do not auto-promote.
        pass
    if not report.get("assert_merge_contiguous_refused", True):
        # On the known-short tip the gate must refuse; fail closed if it does not.
        if (
            report["contiguity"]["unique_id_count"]
            < report["contiguity"]["declared_program_count"]
        ):
            raise SystemExit(
                "IMP-0456: live shortfall present but assert did not refuse"
            )

    rev = load_review()
    # SUCCESS only after independent recount — NEVER invent it here.
    success = rev is not None and report["exact_question"]["answer"] is True

    c = report["contiguity"]
    inv = report["inventory"]
    eq = report["exact_question"]

    p_pytest = L.probe(
        "source",
        "test-run",
        f"python3 -m pytest {TESTS} {LEGACY_TESTS} -q --tb=line",
        out,
        rc,
    )
    p_meas = L.probe("verifier", "command", f"python3 -B {MEASURE}", m_out, m_rc)

    gaps = c.get("total_gap_count", 0)
    dups = inv.get("duplicate_count", 0)
    unique = c.get("unique_id_count")
    declared = c.get("declared_program_count")

    if success:
        state = "SUCCESS"
        sentinel = "SENTINEL:IMP-0456:CATALOG-MERGE-CONTIGUOUS"
        notes = rev.get("notes", "")
        if not isinstance(notes, str):
            notes = json.dumps(notes)
        reviewer = {
            "reviewer_id": rev.get("reviewer_id", "independent-claude-reviewer"),
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": notes[:4000],
        }
        residual: list[dict] = []
        failure = None
        anti = "SUCCESS-after-independent-slice-recount"
        downstream = [
            {
                "consumer": "catalog_slice_merge.assert_merge_contiguous",
                "artifact_path": REPORT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_meas,
            }
        ]
    else:
        state = "BLOCKED"
        if rev is not None:
            # Independent recount PASS, but live tree is not contiguous-unique-exact.
            notes = rev.get("notes", "")
            if not isinstance(notes, str):
                notes = json.dumps(notes)
            vendor = rev.get("vendor", "anthropic")
            if vendor not in ("anthropic", "openai", "human", "codex", "claude"):
                vendor = "anthropic"
            reviewer = {
                "reviewer_id": rev.get("reviewer_id", "independent-claude-reviewer"),
                "verdict": "PASS",
                "independent": True,
                "fresh_context": True,
                "vendor": vendor,
                "reviewed_at": rev.get("reviewed_at", ended),
                "notes": notes[:4000],
            }
            sentinel = (
                f"FAILED:{UNIT} blocked-on-live-shortfall; "
                f"unique={unique} declared={declared} gaps={gaps} dups={dups}; "
                f"exact_question_answer={eq.get('answer')}; "
                f"independent recount PASS; "
                f"SUCCESS:{UNIT} withheld until ids contiguous/unique/exact "
                f"(SENTINEL:IMP-0456:CATALOG-MERGE-CONTIGUOUS withheld)"
            )
            residual = [
                {
                    "claim": (
                        "Live catalog slices are not contiguous-unique-exact "
                        f"(unique={unique} declared={declared} gaps={gaps})."
                    ),
                    "verdict": "REFUTED",
                    "settling_experiment": (
                        "Slice authors fill the shortfall (or revise declared "
                        "program count) so exact_question.answer becomes true; "
                        "then re-pack may emit SENTINEL:IMP-0456:CATALOG-MERGE-CONTIGUOUS."
                    ),
                }
            ]
            failure = {
                "classification": [
                    "index-gap",
                    "P1-blocking / classes: duplicate-unit-id, index-gap, count-claimed-not-read",
                ],
                "reason": (
                    "Independent per-slice recount PASS confirms merge report "
                    f"(unique={unique} declared={declared} gaps={gaps} dups={dups}). "
                    "SUCCESS requires exact_question.answer=true; live shortfall "
                    "keeps this unit BLOCKED. SUCCESS not invented."
                ),
                "blocked_on": "live catalog shortfall (gaps!=0 vs declared program count)",
                "diagnostic_tail": (out + "\n" + m_out + "\n" + notes)[-4000:],
                "two_signal_proof": [p_pytest, p_meas],
            }
            anti = "BLOCKED-after-recount-PASS-live-gaps"
        else:
            sentinel = (
                f"FAILED:{UNIT} blocked-on-independent-review; "
                f"unique={unique} declared={declared} gaps={gaps} dups={dups}; "
                f"exact_question_answer={eq.get('answer')}; "
                f"assert_refused={report.get('assert_merge_contiguous_refused')}; "
                f"block_reasons={report.get('block_reasons')}; "
                f"planted dup/gap/clean controls green; "
                f"SUCCESS:{UNIT} withheld pending independent-claude-reviewer "
                f"per-slice recount from disk; "
                f"SENTINEL:IMP-0456:CATALOG-MERGE-CONTIGUOUS withheld"
            )
            reviewer = {
                "reviewer_id": "awaiting-independent-claude-reviewer",
                "verdict": "NOT-REVIEWED",
                "independent": False,
                "fresh_context": False,
                "vendor": "anthropic",
                "reviewed_at": ended,
                "notes": (
                    "Implementer emit only on Linux Cloud single-checkout. Catalog "
                    "reviewer_requirement unmet: independent-claude-reviewer must "
                    "recount each catalog-slices/*.json independently from the "
                    "files on disk (per-slice count, id range, gaps, duplicates) "
                    "and confirm the merge report. Self-review banned; "
                    "independent-review.json not invented; SUCCESS not invented. "
                    f"Measured: unique={unique} declared={declared} gaps={gaps} "
                    f"dups={dups} merge_allowed={report.get('merge_allowed')} "
                    f"block_reasons={report.get('block_reasons')}. Live shortfall "
                    "means contiguous-unique-exact is currently FALSE — packing "
                    "BLOCKED is honest even after planted controls are green. "
                    f"Dependency IMP-0436 verified {dep['state']}. "
                    "Prompt-One Windows trees unmounted."
                ),
            }
            residual = [
                {
                    "claim": (
                        "Independent Claude reviewer has not recounted each slice "
                        "from disk against the merge report."
                    ),
                    "verdict": "NOT-CHECKED",
                    "settling_experiment": (
                        "Fresh-context independent-claude-reviewer re-reads every "
                        "command-center/catalog-slices/*.json, recounts per-slice "
                        f"counts/ranges/gaps/dups, compares to {REPORT}, and writes "
                        f"{PROBE_DIR}/independent-review.json with verdict=PASS, "
                        "independent=true, fresh_context=true, "
                        "recounted_each_slice_from_disk=true. SUCCESS may emit "
                        "only when that review PASSes AND exact_question.answer "
                        "is true (ids contiguous, unique, equal to declared "
                        "program count); until the live shortfall/gaps are closed, "
                        "remain BLOCKED even with a PASS review of the refusal."
                    ),
                }
            ]
            failure = {
                "classification": [
                    "blocked-on-independent-review",
                    "P1-blocking / classes: duplicate-unit-id, index-gap, count-claimed-not-read",
                ],
                "reason": (
                    "Merger + gap/duplicate reporting + planted controls are green "
                    f"(pytest rc={rc}; measure rc={m_rc}; "
                    f"unique={unique} declared={declared} gaps={gaps} dups={dups}; "
                    f"assert_refused={report.get('assert_merge_contiguous_refused')}). "
                    "Catalog reviewer_requirement demands an independent per-slice "
                    "recount from disk; do not emit SUCCESS without that. Live "
                    "tree is not contiguous-unique-exact — refusing SUCCESS is "
                    "also required by the evidence rule (nonzero gap blocks merge)."
                ),
                "blocked_on": (
                    "independent-claude-reviewer (per-slice recount from disk)"
                ),
                "diagnostic_tail": (out + "\n" + m_out)[-4000:],
                "two_signal_proof": [p_pytest, p_meas],
            }
            anti = "BLOCKED-pending-independent-slice-recount"
        downstream = [
            {
                "consumer": "catalog_slice_merge.build_merge_report",
                "artifact_path": REPORT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_meas,
            },
            {
                "consumer": "catalog_slice_merge.assert_merge_contiguous",
                "artifact_path": REPORT,
                "executed": True,
                "read_ok": True,
                "exit_code": 1 if report.get("assert_merge_contiguous_refused") else 0,
                "probe": p_meas,
            },
            {
                "consumer": "planted-controls-pytest",
                "artifact_path": f"{PROBE_DIR}/pytest.out",
                "executed": True,
                "read_ok": True,
                "exit_code": rc,
                "probe": p_pytest,
            },
        ]

    arts = [
        L.art(MERGER, "primary"),
        L.art(TESTS, "supporting"),
        L.art(LEGACY_TESTS, "supporting"),
        L.art(REPORT, "log"),
        L.art(f"{PROBE_DIR}/pytest.out", "log"),
        L.art(f"{PROBE_DIR}/measure.out", "log"),
        L.art(f"{PROBE_DIR}/_pack_receipt.py", "control"),
        L.art(MEASURE, "control"),
        L.art(DEP, "supporting"),
    ]
    if success or rev is not None:
        arts.append(L.art(f"{PROBE_DIR}/independent-review.json", "supporting"))

    # Per-prefix gap summary for report.observations (cap size).
    gap_prefixes = [
        {
            "prefix": row["prefix"],
            "gap_count": row["gap_count"],
            "gaps_sample": row["gaps"][:12],
            "unique": row["unique"],
            "quota": row["quota_units"],
        }
        for row in c.get("per_prefix", [])
        if row.get("gap_count")
    ]

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#IMP-0456",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "tooling-implementer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    "Extended tools/command-center/catalog_slice_merge.py with "
                    "ContiguityError, build_merge_report (per-slice count/range, "
                    "gaps, duplicates, total vs declared floor), mechanism "
                    "collision scan, and assert_merge_contiguous / "
                    "--require-contiguous refuse-on-gap-or-dup gate."
                ),
                "CONFIRMED",
                f"file:{MERGER}",
                [p_pytest, p_meas],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Merge report: unique={unique} declared={declared} "
                    f"gaps={gaps} dups={dups} "
                    f"merge_allowed={report.get('merge_allowed')} "
                    f"block_reasons={report.get('block_reasons')} "
                    f"assert_refused={report.get('assert_merge_contiguous_refused')}. "
                    "Any nonzero gap or duplicate blocks the merge."
                ),
                "CONFIRMED",
                f"file:{REPORT}",
                [p_meas, p_pytest],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Planted controls: planted-duplicate raises CollisionError; "
                    "planted-gap raises ContiguityError; clean mini-allocation "
                    "slice set merges (positive control). Live slices honestly "
                    "fail the contiguous gate (shortfall/gaps)."
                ),
                "CONFIRMED",
                f"file:{TESTS}",
                [p_pytest, p_meas],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "max 2 attempts, backoff 30s/120s; independent recount disputes "
                "require a fresh reviewer, not a third implementer SUCCESS invent."
            ),
        },
        "tests": [
            {
                "id": "planted-duplicate-blocks",
                "name": "Planted duplicate id must block the merge.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_planted_duplicate_must_block_merge -q"
                ),
                "result": "PASS" if rc == 0 else "FAIL",
                "assertions": 4,
                "output_tail": out[-800:],
            },
            {
                "id": "planted-gap-blocks",
                "name": "Planted index gap must block the merge.",
                "command": (
                    f"python3 -m pytest {TESTS}::test_planted_gap_must_block_merge -q"
                ),
                "result": "PASS" if rc == 0 else "FAIL",
                "assertions": 5,
                "output_tail": out[-800:],
            },
            {
                "id": "clean-slice-set-merges",
                "name": "Clean contiguous slice set must merge (positive control).",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_clean_slice_set_must_merge_positive_control -q"
                ),
                "result": "PASS" if rc == 0 else "FAIL",
                "assertions": 6,
                "output_tail": out[-800:],
            },
            {
                "id": "live-slices-refuse-contiguous",
                "name": "Live shortfall/gaps must fail contiguous gate (honest).",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_live_slices_honestly_fail_contiguous_gate -q"
                ),
                "result": "PASS"
                if report.get("assert_merge_contiguous_refused")
                else "FAIL",
                "assertions": 6,
                "output_tail": m_out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "planted-duplicate-blocks",
                "known-broken-fixture",
                "Two slices claiming the same id must raise CollisionError.",
                True,
                True,
                bad="CC-0001 claimed by colliding slices",
                good="clean mini-alloc merge_allowed=true",
            ),
            L.control(
                "planted-gap-blocks",
                "known-broken-fixture",
                "Missing index inside 1..quota must raise ContiguityError.",
                True,
                True,
                bad="IMP gaps include 2",
                good="clean mini-alloc contiguous_unique_exact=true",
            ),
            L.control(
                "clean-positive-control-merges",
                "mutation",
                "A contiguous unique exact mini slice set must merge (proves not always-refuse).",
                True,
                True,
                bad="would refuse everything",
                good="mini floor=4 merge write work_unit_count=4",
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
            "kind": "catalog-slice-merge-contiguity",
            "observations": [
                {
                    "name": "exact_question",
                    "measured": eq,
                    "method": "build_merge_report + assert_merge_contiguous",
                    "anchor": REPORT,
                },
                {
                    "name": "totals",
                    "measured": {
                        "unique": unique,
                        "declared": declared,
                        "gaps": gaps,
                        "dups": dups,
                        "quota_shortfall": c.get("total_quota_shortfall"),
                    },
                    "method": "scan_slice_id_inventory + analyze_contiguity",
                    "anchor": REPORT,
                },
                {
                    "name": "gap_prefixes",
                    "measured": gap_prefixes,
                    "method": "per-prefix 1..quota scan",
                    "anchor": REPORT,
                },
                {
                    "name": "dependency_IMP_0436",
                    "measured": dep,
                    "method": "receipt state read",
                    "anchor": DEP,
                },
            ],
            "control_ids": [
                "planted-duplicate-blocks",
                "planted-gap-blocks",
                "clean-slice-set-merges",
                "live-slices-refuse-contiguous",
            ],
            "reviewer_requirement": {
                "required": "independent-claude-reviewer recounts each slice from disk",
                "independent_review_present": REVIEW.is_file(),
                "review_loaded": rev is not None,
            },
            "scope": {
                "execution_substrate": "linux-cloud-agent",
                "checkout": "single",
                "live_catalog_write": False,
                "success_invented": False,
            },
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": f"{PROBE_DIR}/_pack_receipt.py",
            "anti_false_green": anti,
            "linux_cloud_scope": True,
            "catalog_completion_sentinel": "SENTINEL:IMP-0456:CATALOG-MERGE-CONTIGUOUS",
            "success_invented": False,
            "independent_review_invented": False,
            "dependency_verified": dep,
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
                    MERGER,
                    TESTS,
                    REPORT,
                    MEASURE,
                    DEP,
                ],
                "state": state,
                "registered_at": ended,
                "reviewer_requirement": (
                    "independent-claude-reviewer recounts each slice "
                    "independently from the files on disk"
                ),
                "success_invented": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    rc_w = L.write_if_valid(receipt, OUT, SCHEMA, also=ALSO)
    if rc_w != 0:
        raise SystemExit(rc_w)
    receipt["artifacts"].insert(0, L.art(OUT, "primary"))
    rc2 = L.write_if_valid(receipt, OUT, SCHEMA, also=ALSO)
    if rc2 != 0:
        raise SystemExit(rc2)

    v_rc2, v_out2 = _run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    (L.REPO / PROBE_DIR / "receipt-validate.out").write_text(v_out2, encoding="utf-8")
    if v_rc2 != 0 or "ACCEPT" not in v_out2:
        raise SystemExit(f"receipt_validate rejected:\n{v_out2}")

    print(f"PACKED {OUT} state={state} bytes={L.art(OUT)['bytes']}")
    print(
        f"unique={unique} declared={declared} gaps={gaps} dups={dups} "
        f"exact_answer={eq.get('answer')} success_invented=False"
    )
    print(f"independent_review={REVIEW.is_file()} (must stay false for this emit)")
    return receipt


if __name__ == "__main__":
    build()
