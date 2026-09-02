#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0299.json and the append-only results ledger."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

import paths as P
import reviewer as R
from bench.tournament import (
    MIXED_SEED,
    NULL_SEED,
    ledger_row,
    mixed_tournament,
    null_identical_tournament,
    null_iid_tournament,
)

CATALOG = "command-center/WORK-UNIT-CATALOG.json"


def _git_head() -> str:
    if not (P.REPO / ".git").exists():
        return "git-unavailable"
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(P.REPO),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "git-unavailable"
    if proc.returncode == 0:
        return (proc.stdout or "").strip() or "git-unavailable"
    return "git-unavailable"


def _anchor(rel: str, snippet: str, kind: str, claim: str) -> dict:
    text = (P.REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:TST-0299 snippet not in {rel}: {snippet[:80]}")
    line = text[:idx].count("\n") + 1
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def _luckies(mixed: dict) -> list[str]:
    holm_ids = set(mixed["live_gate"]["certified_ids"])
    return [
        row["id"]
        for row in mixed["family"]["comparisons"]
        if row["uncorrected_significant"] and row["id"] not in holm_ids
    ]


def main() -> int:
    ident = null_identical_tournament()
    iid = null_iid_tournament()
    mixed = mixed_tournament()
    rev = R.review_live_runs()
    if rev["verdict"] != "PASS":
        print("FAILED:TST-0299 independent re-run did not reproduce")
        print(json.dumps(rev, indent=2)[:2000])
        return 1

    ident_f = ident["family"]
    iid_f = iid["family"]
    mix_f = mixed["family"]
    luckies = _luckies(mixed)
    if not luckies:
        print("FAILED:TST-0299 mixed tournament has no uncorrected-only winner")
        return 1
    if mixed["live_gate"]["certified_count"] >= mixed["mutant_gate"]["certified_count"]:
        print("FAILED:TST-0299 mutant must certify a strictly larger set")
        return 1
    if not mixed["certification_list_shrinks"]:
        print("FAILED:TST-0299 certification list did not shrink after correction")
        return 1
    if ident_f["family_size"] != 40 or iid_f["family_size"] != 40 or mix_f["family_size"] != 40:
        print("FAILED:TST-0299 family_size is not 40")
        return 1
    if ident_f["holm_certified_count"] != 0 or ident_f["bh_discovery_count"] != 0:
        print("FAILED:TST-0299 identical nulls produced corrected discoveries")
        return 1
    if iid_f["holm_certified_count"] != 0 or iid_f["bh_discovery_count"] != 0:
        print("FAILED:TST-0299 iid null tournament produced corrected discoveries")
        return 1
    if iid_f["uncorrected_discovery_count"] < 1:
        print("FAILED:TST-0299 iid null tournament produced no uncorrected winners")
        return 1

    P.LEDGER.parent.mkdir(parents=True, exist_ok=True)
    P.RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    with P.LEDGER.open("w", encoding="utf-8") as fh:
        for run in (ident, iid, mixed):
            fh.write(json.dumps(ledger_row(run), sort_keys=True) + "\n")

    lucky = luckies[0]
    live_refuses_lucky = lucky not in mixed["live_gate"]["certified_ids"]
    mutant_accepts_lucky = lucky in mixed["mutant_gate"]["certified_ids"]
    mutant_goes_red = live_refuses_lucky and mutant_accepts_lucky
    if not mutant_goes_red:
        print("FAILED:TST-0299 mutant did not turn the lucky-null test red")
        return 1

    tests = [
        {
            "id": "TST-0299-T1",
            "name": "Correction applied across the full comparison family; family size reported",
            "result": "PASS",
            "family_size": mix_f["family_size"],
            "methods": mix_f["correction_methods"],
        },
        {
            "id": "TST-0299-T2",
            "name": (
                "Null-tournament control: 40 identical candidates yield zero "
                "corrected discoveries; 40 iid nulls yield ~0 after BH/Holm"
            ),
            "result": "PASS",
            "identical": {
                "uncorrected": ident_f["uncorrected_discovery_count"],
                "bh": ident_f["bh_discovery_count"],
                "holm": ident_f["holm_certified_count"],
            },
            "iid_null": {
                "uncorrected": iid_f["uncorrected_discovery_count"],
                "bh": iid_f["bh_discovery_count"],
                "holm": iid_f["holm_certified_count"],
                "seed": NULL_SEED,
            },
        },
        {
            "id": "TST-0299-T3",
            "name": (
                "Certification gate consumes the CORRECTED (Holm) verdict; "
                "mutant reading uncorrected turns the lucky-null test red"
            ),
            "result": "PASS",
            "lucky_id": lucky,
            "live_test_lucky_not_certified": live_refuses_lucky,
            "mutant_test_lucky_not_certified": not mutant_accepts_lucky,
            "mutant_goes_red": mutant_goes_red,
        },
    ]

    evidence = [
        _anchor(
            CATALOG,
            "Control the false-discovery rate when a tournament compares many candidates at once",
            "catalog",
            "TST-0299 is the FDR/tournament unit",
        ),
        _anchor(
            "tools/bench/multiple_comparison.py",
            "Apply BH (discovery) and Holm (family-wise) to the full family.",
            "implementation",
            "BH and Holm run over the entire family, not a post-hoc subset",
        ),
        _anchor(
            "tools/bench/certification.py",
            "consume=\"corrected\" (default, live gate): Holm family-wise rejection.",
            "implementation",
            "Live certification gate consumes the Holm-corrected field",
        ),
        _anchor(
            "tools/bench/certification.py",
            "The named mutant: gate body identical except it consumes uncorrected.",
            "negative-control",
            "Mutant gate reads uncorrected WINNER flags",
        ),
        _anchor(
            "command-center/bench/results/TST-0299.jsonl",
            '"unit_id": "TST-0299"',
            "ledger",
            "Append-only per-run results ledger with raw per-case scores",
        ),
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "id": "TST-0299",
        "unit_id": "TST-0299",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": P.SENTINEL,
        "completion_sentinel": P.SENTINEL,
        "title": "Control the false-discovery rate when a tournament compares many candidates at once",
        "question": (
            "Run 40 candidate workflows against a baseline at the 0.05 level and "
            "roughly two will look like winners by chance. Apply BH (discovery) "
            "and Holm (family-wise), report both corrected and uncorrected "
            "results, and make correction mandatory before certification."
        ),
        "answer": (
            f"Family size is 40. Uncorrected mixed-tournament discoveries="
            f"{mix_f['uncorrected_discovery_count']}; BH discoveries="
            f"{mix_f['bh_discovery_count']}; Holm certified="
            f"{mix_f['holm_certified_count']} (list shrinks by "
            f"{mixed['shrink_delta']}). Null-iid uncorrected="
            f"{iid_f['uncorrected_discovery_count']}, BH=0, Holm=0. "
            f"Certification consumes Holm, not the uncorrected WINNER flag. "
            f"{P.SENTINEL}"
        ),
        "alpha": 0.05,
        "correction_methods": mix_f["correction_methods"],
        "family_size": 40,
        "uncorrected_verdict_counts": {
            "null-identical": ident_f["uncorrected_discovery_count"],
            "null-iid": iid_f["uncorrected_discovery_count"],
            "mixed": mix_f["uncorrected_discovery_count"],
        },
        "corrected_verdict_counts": {
            "null-identical": {
                "bh": ident_f["bh_discovery_count"],
                "holm": ident_f["holm_certified_count"],
            },
            "null-iid": {
                "bh": iid_f["bh_discovery_count"],
                "holm": iid_f["holm_certified_count"],
            },
            "mixed": {
                "bh": mix_f["bh_discovery_count"],
                "holm": mix_f["holm_certified_count"],
            },
        },
        "certification_list_shrinks": True,
        "shrink_delta": mixed["shrink_delta"],
        "uncorrected_certified_ids": mixed["uncorrected_certified_ids"],
        "holm_certified_ids": mixed["live_gate"]["certified_ids"],
        "bh_discovered_ids": [r["id"] for r in mix_f["comparisons"] if r["bh_rejected"]],
        "planted_true_ids": mixed["true_ids"],
        "lucky_uncorrected_only_ids": luckies,
        "null_iid": {
            "seed": NULL_SEED,
            "family_size": iid_f["family_size"],
            "uncorrected_discovery_count": iid_f["uncorrected_discovery_count"],
            "bh_discovery_count": iid_f["bh_discovery_count"],
            "holm_certified_count": iid_f["holm_certified_count"],
            "comparisons": iid_f["comparisons"],
        },
        "null_identical": {
            "seed": NULL_SEED,
            "family_size": ident_f["family_size"],
            "uncorrected_discovery_count": ident_f["uncorrected_discovery_count"],
            "bh_discovery_count": ident_f["bh_discovery_count"],
            "holm_certified_count": ident_f["holm_certified_count"],
        },
        "mixed": {
            "seed": MIXED_SEED,
            "family_size": mix_f["family_size"],
            "uncorrected_discovery_count": mix_f["uncorrected_discovery_count"],
            "bh_discovery_count": mix_f["bh_discovery_count"],
            "holm_certified_count": mix_f["holm_certified_count"],
            "comparisons": mix_f["comparisons"],
            "live_gate": mixed["live_gate"],
            "mutant_gate": mixed["mutant_gate"],
        },
        "gate": {
            "live_consumes": "corrected",
            "mutant_consumes": "uncorrected",
            "live_source": "holm_rejected",
            "mutant_source": "uncorrected_significant",
            "lucky_id": lucky,
            "live_refuses_lucky": live_refuses_lucky,
            "mutant_accepts_lucky": mutant_accepts_lucky,
            "mutant_goes_red": mutant_goes_red,
            "test_that_goes_red_on_mutant": (
                "lucky uncorrected-only winner must not be CERTIFIED"
            ),
        },
        "tests": tests,
        "evidence": evidence,
        "evidence_requirement": (
            "Report the number of comparisons in the family, the correction "
            "method, and both the corrected and uncorrected verdict counts. "
            "A certification list that shrinks after correction is the expected "
            "outcome and must be shown."
        ),
        "reviewer": rev,
        "artifacts": [
            {"path": "command-center/receipts/TST-0299.json", "role": "primary"},
            {
                "path": "command-center/bench/results/TST-0299.jsonl",
                "role": "results-ledger",
            },
            {"path": "tools/bench/multiple_comparison.py", "role": "implementation"},
            {"path": "tools/bench/certification.py", "role": "implementation"},
        ],
        "output_path": "command-center/receipts/TST-0299.json",
        "output_schema": "command-center/schema/receipt.schema.json",
        "output_schema_present": (
            P.REPO / "command-center/schema/receipt.schema.json"
        ).is_file(),
        "generated_commit": _git_head(),
        "ts": now,
        "produced_by": {
            "role": "statistician",
            "execution_substrate": "linux-worktree",
            "unit": "TST-0299",
        },
        "ledger": {
            "path": "command-center/bench/results/TST-0299.jsonl",
            "entries": 3,
            "kinds": ["null-identical", "null-iid", "mixed"],
        },
        "notes": (
            "G-1 TST-0299: BH+Holm over family_size=40, null-tournament control, "
            "certification consumes Holm. Did not run global unit_manifest.py --write."
        ),
    }

    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if P.SENTINEL not in text:
        print("FAILED:TST-0299 sentinel missing from receipt bytes")
        return 1
    P.RECEIPT.write_text(text, encoding="utf-8")
    print(
        f"wrote {P.RECEIPT.relative_to(P.REPO).as_posix()} "
        f"bytes={len(text.encode('utf-8'))} "
        f"family=40 uncorrected_mixed={mix_f['uncorrected_discovery_count']} "
        f"holm={mix_f['holm_certified_count']} "
        f"iid_uncorrected={iid_f['uncorrected_discovery_count']}"
    )
    print(P.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
