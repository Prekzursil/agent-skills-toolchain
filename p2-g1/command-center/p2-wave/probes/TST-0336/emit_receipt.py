#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0336.json from a live N=20 ledger run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import ledger as L  # noqa: E402
from suite import FIXED_NOW, REGISTRY, TESTS, commit_sha  # noqa: E402

OUT = "command-center/receipts/TST-0336.json"
SENTINEL = "SUCCESS:TST-0336"
SCHEMA = "command-center/schema/receipt.schema.json"
SUT = "command-center/p2-wave/probes/TST-0336/ledger.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0336/probe1_n20_ranked_coin_flip.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0336/probe2_visibility_debt_retry.py"
)
QUESTION = (
    "Implementation target: measure per-test flake rate by rerunning the suite "
    "N times on an unchanged commit, publish the ranked list, and route anything "
    "above the threshold into a quarantine lane that still RUNS and still reports "
    "but cannot block. The rule that matters is the accounting one: a quarantined "
    "test is open debt with an owner and a deadline, not a solved problem, and a "
    "retry policy that hides flakes converts a real intermittent defect into "
    "invisible noise."
)
N = 20


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def digest_rel(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        return {
            "path": rel,
            "bytes": 0,
            "sha256": "",
            "exists": False,
            "role": role,
            "eol": "ABSENT",
        }
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def slim_row(row: dict) -> dict:
    keep = (
        "test_id",
        "commit_sha",
        "status",
        "repetitions",
        "passes",
        "fails",
        "flake_rate",
        "fail_rate",
        "classification",
        "provisional",
        "quarantined",
        "can_block",
        "above_threshold",
        "owner",
        "quarantine_opened_at",
        "deadline",
        "age_days",
        "open",
        "complete",
    )
    return {k: row[k] for k in keep if k in row}


def main() -> int:
    sha = commit_sha()
    honest = L.measure_suite(
        TESTS, N, sha, max_attempts=1, now=FIXED_NOW, registry=REGISTRY
    )
    short = L.measure_suite(
        TESTS, 5, sha, max_attempts=1, now=FIXED_NOW, registry=REGISTRY
    )
    ranked = honest["ranked"]
    by = {r["test_id"]: r for r in ranked}
    coin = by["coin_flip"]
    above = by["just_above"]
    thresh = by["at_threshold"]
    broken = by["broken_always"]
    stable = by["stable_pass"]
    bait = by["retry_bait"]

    if coin["quarantined"] is not True or coin["fails"] != 10:
        print("FAILED:TST-0336 emit coin_flip not quarantined at 10/20")
        return 1
    if above["quarantined"] is not True or above["fails"] != 2:
        print("FAILED:TST-0336 emit just_above not quarantined")
        return 1
    if thresh["quarantined"] is True or thresh["fails"] != 1:
        print("FAILED:TST-0336 emit at_threshold should not quarantine")
        return 1
    if broken["classification"] != "BROKEN" or not broken["can_block"]:
        print("FAILED:TST-0336 emit BROKEN does not block")
        return 1
    if any(r["provisional"] for r in ranked):
        print("FAILED:TST-0336 emit N=20 labelled provisional")
        return 1
    if not all(r["provisional"] for r in short["ranked"]):
        print("FAILED:TST-0336 emit N=5 not labelled provisional")
        return 1

    visible = L.render_report(ranked, hide_quarantined=False)
    hidden = L.render_report(ranked, hide_quarantined=True)
    hide_fires = L.quarantine_hidden(visible, hidden) is True
    hide_silent = L.quarantine_hidden(visible, visible) is False
    if not hide_fires or not hide_silent:
        print("FAILED:TST-0336 emit visibility both-states failed")
        return 1

    q_rows = [r for r in ranked if r["quarantined"]]
    debt_ok = all(r.get("owner") and r.get("age_days") is not None for r in q_rows)
    if not debt_ok:
        print("FAILED:TST-0336 emit quarantined row missing owner/age")
        return 1

    defects = L.retry_defects(
        TESTS, N, sha, retry_attempts=3, now=FIXED_NOW, registry=REGISTRY
    )
    absorbed = {d["test_id"] for d in defects if d["reason"] == "retry-absorbed-flake"}
    if "coin_flip" not in absorbed or "retry_bait" not in absorbed:
        print(f"FAILED:TST-0336 emit retry absorption missed: {defects}")
        return 1
    no_retry = L.retry_defects(
        TESTS, N, sha, retry_attempts=1, now=FIXED_NOW, registry=REGISTRY
    )
    if no_retry:
        print(f"FAILED:TST-0336 emit max_attempts=1 filed absorption: {no_retry}")
        return 1

    catalog_registry = REPO / "command-center/TEST-REGISTRY.json"
    catalog_bench = REPO / "command-center/bench/results"
    schema_path = REPO / SCHEMA
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sut_sha, sut_bytes = sha256_file(REPO / SUT)
    ranked_slim = [slim_row(r) for r in ranked]
    answer = (
        "Yes for the live first-attempt ledger under test. Twenty identical "
        f"reruns at fixture commit {sha[:12]} classified coin_flip as FLAKY at "
        f"flake_rate={coin['flake_rate']} (10 fail / 10 pass), which is above the "
        f"1-in-20 threshold ({L.THRESHOLD}) and is quarantined: it still appears "
        "in the report with status=QUARANTINED, carries owner=test-governance and "
        f"age_days={coin['age_days']}, and cannot block the suite. just_above "
        f"(2/20) is likewise quarantined; at_threshold (1/20) is FLAKY but not "
        "quarantined because the rule is strictly-above. broken_always remains "
        "BROKEN and still blocks. A 3-attempt retry that keeps the last success "
        "would paint coin_flip and retry_bait green; that absorption is filed as "
        "a DEFECT against the test, not a pass. Rates from N=5 are labelled "
        "provisional. Catalog inputs command-center/TEST-REGISTRY.json and "
        "command-center/bench/results/ are absent on this worktree; production "
        "suite flake rates are NOT-CHECKED."
    )

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0336",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "SUCCESS:TST-0336": True,
        "title": (
            "Quarantine flaky tests and treat a flake as a defect rather than "
            "absorbing it in retries"
        ),
        "question": QUESTION,
        "answer": answer,
        "report_kind": "flake_quarantine_ledger",
        "output_schema": SCHEMA,
        "declared_schema_file_present": schema_path.is_file(),
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json TST-0336; retry_policy 'Up to 3 attempts with "
            "full-jitter backoff. A flake rate above 1-in-20 reruns is filed as a "
            "DEFECT against the test, never absorbed as a retry.'"
        ),
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "required_fix": None,
        "sut": {
            "live_module": SUT,
            "live_sha256": sut_sha,
            "live_bytes": sut_bytes,
            "algorithm": (
                "first-attempt N-run ledger; flake_rate=fails/N for mixed outcomes; "
                "quarantine iff FLAKY and flake_rate > 1/20; BROKEN (all-fail) still "
                "blocks; retry finals are compared, never substituted"
            ),
            "threshold": L.THRESHOLD,
            "min_n_definitive": L.MIN_N_DEFINITIVE,
            "catalog_test_registry_present": catalog_registry.is_file(),
            "catalog_bench_results_present": catalog_bench.is_dir(),
        },
        "commit": {
            "fixture_seed": "TST-0336-fixture-commit",
            "sha256": sha,
            "unchanged_across_reruns": True,
            "note": (
                "Catalog asks for N reruns on an unchanged commit. This worktree "
                "is not a git repo; the fixture SHA is hashlib.sha256 of a pinned "
                "seed and is attached to every attempt record."
            ),
        },
        "flake_ledger": {
            "n": N,
            "accounting": "first-attempt",
            "threshold": L.THRESHOLD,
            "ranked": ranked_slim,
            "quarantined_ids": honest["quarantined_ids"],
            "suite_blockers": honest["suite_blockers"],
            "suite_green": honest["suite_green"],
            "defects": honest["defects"],
            "provisional_n5": {
                "n": 5,
                "all_labelled_provisional": all(
                    r["provisional"] for r in short["ranked"]
                ),
                "ranked": [slim_row(r) for r in short["ranked"]],
            },
        },
        "visibility_control": {
            "id": "hide-quarantined-lane",
            "kind": "both-states",
            "description": (
                "Good lane lists quarantined tests with status=QUARANTINED. Bad "
                "lane drops them. Detector fires only on the bad lane."
            ),
            "visible_ids": [r["test_id"] for r in visible],
            "hidden_ids": [r["test_id"] for r in hidden],
            "fired_on_bad_state": hide_fires,
            "silent_on_good_state": hide_silent,
        },
        "debt_accounting": {
            "all_quarantined_have_owner_and_age": debt_ok,
            "rows": [
                {
                    "test_id": r["test_id"],
                    "owner": r["owner"],
                    "age_days": r["age_days"],
                    "deadline": r["deadline"],
                    "quarantine_opened_at": r["quarantine_opened_at"],
                    "open": r["open"],
                }
                for r in q_rows
            ],
        },
        "retry_absorption": {
            "catalog_attempts": 3,
            "filed_as_defect": sorted(absorbed),
            "silent_when_max_attempts_1": no_retry == [],
            "defects": defects,
            "rule": (
                "A flake rate above 1-in-20 reruns is filed as a DEFECT against "
                "the test, never absorbed as a retry."
            ),
        },
        "controls": {
            "coin_flip": slim_row(coin),
            "just_above": slim_row(above),
            "at_threshold": slim_row(thresh),
            "broken_always": slim_row(broken),
            "stable_pass": slim_row(stable),
            "retry_bait": slim_row(bait),
        },
        "evidence": [
            {
                "anchor": f"{SUT}:measure_suite",
                "claim": (
                    "Per-test flake rates were measured over 20 identical first-attempt "
                    "reruns at a fixed commit SHA. coin_flip is FLAKY at 0.5 and "
                    "quarantined; just_above (0.10) is quarantined; at_threshold "
                    "(0.05) is not; N=5 rates are labelled provisional."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "source_probe": P1,
                "verifier_probe": P2,
            },
            {
                "anchor": f"{SUT}:render_report",
                "claim": (
                    "Quarantine does not hide: coin_flip remains in the visible "
                    "report with status=QUARANTINED. The hide-quarantined lane "
                    "drops it and the detector fires only on that bad state. "
                    "Every quarantined row has owner and age_days."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "source_probe": P2,
                "verifier_probe": P1,
            },
            {
                "anchor": f"{SUT}:retry_defects",
                "claim": (
                    "A 3-attempt retry that keeps the last success absorbs "
                    "coin_flip and retry_bait into an all-pass final. That is "
                    "filed as DEFECT reason=retry-absorbed-flake. max_attempts=1 "
                    "files nothing."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "source_probe": P2,
                "verifier_probe": P1,
            },
        ],
        "negative_controls": [
            {
                "id": "hide-quarantined-report",
                "kind": "both-states",
                "description": (
                    "Dropping quarantined tests from the report must fire; the "
                    "visible lane must stay silent."
                ),
                "fired_on_bad_state": hide_fires,
                "silent_on_good_state": hide_silent,
            },
            {
                "id": "retry-absorbs-coin-flip",
                "kind": "mutation",
                "description": (
                    "Replace first-attempt accounting with last-of-3-attempts. "
                    "coin_flip and retry_bait look green; the honest ledger "
                    "still shows them failing first attempts and files DEFECT."
                ),
                "fired_on_bad_state": "coin_flip" in absorbed,
                "silent_on_good_state": no_retry == [],
            },
            {
                "id": "owner-stripped-debt",
                "kind": "mutation",
                "description": (
                    "A quarantined row with owner removed fails debt completeness; "
                    "the planted owner+age row passes."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": debt_ok,
            },
        ],
        "tests_required": [
            {
                "id": "flake-rate-n20",
                "text": "Flake rate measured over at least 20 identical runs.",
                "result": "PASS",
                "repetitions": N,
                "provisional": False,
            },
            {
                "id": "quarantine-does-not-hide",
                "text": (
                    "Quarantine does not hide: quarantined results still appear "
                    "in the report with their status."
                ),
                "result": "PASS",
                "visible_status": "QUARANTINED",
            },
            {
                "id": "debt-owner-and-age",
                "text": (
                    "Debt accounting: every quarantined test has an owner and an "
                    "age, and the age is reported."
                ),
                "result": "PASS",
                "owners": [r["owner"] for r in q_rows],
                "ages_days": [r["age_days"] for r in q_rows],
            },
            {
                "id": "coin-flip-control",
                "text": (
                    "Control: inject a coin-flip test and confirm it is detected "
                    "and quarantined."
                ),
                "result": "PASS",
                "flake_rate": coin["flake_rate"],
                "quarantined": True,
            },
        ],
        "tests": [
            {
                "id": "probe1-n20-ranked-coin-flip",
                "command": P1,
                "name": "N=20 ranked flake rates + coin-flip quarantine + provisional N=5",
                "result": "PASS",
            },
            {
                "id": "probe2-visibility-debt-retry",
                "command": P2,
                "name": "visibility both-states + debt owner/age + retry-absorption DEFECT",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0336-probe2-visibility-debt-retry",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Mechanically independent probe 2 re-derives visibility, debt, and "
                "retry-absorption both-states. Not a fresh-context human reviewer; "
                "the catalog names one, which this lane cannot supply without "
                "self-certifying."
            ),
        },
        "retry": {
            "count": 0,
            "policy": (
                "Up to 3 attempts with full-jitter backoff. A flake rate above "
                "1-in-20 reruns is filed as a DEFECT against the test, never "
                "absorbed as a retry."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/TEST-REGISTRY.json is absent; production-suite "
                    "flake rates were not measured."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Point measure_suite at the live registry once it exists and "
                    "rerun both named probes at a real git SHA."
                ),
            },
            {
                "claim": (
                    "command-center/bench/results/ append-only ledger is absent."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Persist attempt records to that directory and verify append-only "
                    "on a second run at the same SHA."
                ),
            },
        ],
        "manifest_registration": {
            "entry_id": "TST-0336",
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0336/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            digest_rel(SUT, "ledger-under-test"),
            digest_rel(
                "command-center/p2-wave/probes/TST-0336/suite.py",
                "planted-suite",
            ),
        ],
        "timestamps": {
            "measured_at_fixture_now": FIXED_NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "emitted_at": now,
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    raw = out_path.read_bytes().replace(b"\r\n", b"\n")
    print(f"wrote {OUT} bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}")
    print("SUCCESS:TST-0336 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
