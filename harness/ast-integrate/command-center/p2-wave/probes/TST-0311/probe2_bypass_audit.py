#!/usr/bin/env python3
"""Named probe 2: a merge without a gate decision is caught by ledger audit.

Both-states: a mutant audit that always returns ok misses the planted
bypass. The live audit must flag it. A KEEP-recorded change in the same
range is not a bypass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.audit import audit_commit_range  # noqa: E402
from bench.decision_ledger import DecisionLedger  # noqa: E402
from bench.gate import decide  # noqa: E402
from bench.margin import load_margin_table  # noqa: E402
from bench.paired import paired_from_cases  # noqa: E402
from bench.scenarios import improvement_cases, noop_cases, underpowered_cases  # noqa: E402

UNIT = "TST-0311"
RAW = HERE / "probe2-bypass-audit.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0311-probe2 {msg}")
    return 1


def mutant_silent_audit(
    _commits: Iterable[Mapping[str, Any]],
    _ledger: Any,
) -> dict[str, Any]:
    """The bypass this unit exists to catch: no decision is treated as fine."""
    return {"ok": True, "findings": [], "bypass_ids": [], "checked": 0}


def main() -> int:
    margins = load_margin_table()
    keep_d = decide(
        paired_from_cases(improvement_cases(24), change_id="chg-keep"),
        margins,
    )
    revert_d = decide(
        paired_from_cases(noop_cases(24), change_id="chg-revert"),
        margins,
    )
    insuff_d = decide(
        paired_from_cases(underpowered_cases(4), change_id="chg-insuff"),
        margins,
    )
    keep_d = dict(keep_d)
    keep_d["commit_sha"] = "sha-keep"
    revert_d = dict(revert_d)
    revert_d["commit_sha"] = "sha-revert"
    insuff_d = dict(insuff_d)
    insuff_d["commit_sha"] = "sha-insuff"

    ledger = DecisionLedger()
    ledger.record(keep_d)
    ledger.record(revert_d)
    ledger.record(insuff_d)

    clean = [
        {"change_id": "chg-keep", "commit_sha": "sha-keep", "merged": True},
    ]
    clean_report = audit_commit_range(clean, ledger)
    if not clean_report.get("ok"):
        return fail(f"KEEP-recorded merge was flagged: {clean_report}")

    planted = [
        {"change_id": "chg-keep", "commit_sha": "sha-keep", "merged": True},
        {"change_id": "chg-ghost", "commit_sha": "sha-ghost", "merged": True},
        {"change_id": "chg-revert", "commit_sha": "sha-revert", "merged": True},
        {"change_id": "chg-insuff", "commit_sha": "sha-insuff", "merged": False},
    ]
    live = audit_commit_range(planted, ledger)
    kinds = {f.get("kind") for f in live.get("findings") or []}
    bypass_ids = list(live.get("bypass_ids") or [])
    if "chg-ghost" not in bypass_ids:
        return fail(f"planted merge without a gate decision was not caught: {live}")
    if "BYPASS" not in kinds:
        return fail(f"missing BYPASS finding: {live}")
    if "UNAUTHORIZED-RETENTION" not in kinds:
        return fail(f"REVERT-merged change was not flagged: {live}")
    if "chg-keep" in bypass_ids:
        return fail("KEEP-recorded change treated as bypass")
    if live.get("ok"):
        return fail("audit reported ok on a range that includes a bypass")

    mutant = mutant_silent_audit(planted, ledger)
    if mutant.get("ok") is not True or mutant.get("findings"):
        return fail("silent mutant did not swallow the bypass")
    if "chg-ghost" in (mutant.get("bypass_ids") or []):
        return fail("silent mutant unexpectedly listed the ghost")
    if live.get("ok") == mutant.get("ok"):
        return fail("live audit did not disagree with the silent mutant")

    payload = {
        "pass": True,
        "probe": "probe2-bypass-audit",
        "unit_id": UNIT,
        "clean_ok": True,
        "bypass_caught": True,
        "bypass_ids": bypass_ids,
        "finding_kinds": sorted(kinds),
        "findings": live.get("findings"),
        "checked": live.get("checked"),
        "ledger_size": live.get("ledger_size"),
        "keep_not_bypass": "chg-keep" not in bypass_ids,
        "mutant_misses_bypass": mutant.get("ok") is True,
        "live_disagrees_with_mutant": True,
        "outcomes_recorded": {
            "KEEP": keep_d["outcome"],
            "REVERT": revert_d["outcome"],
            "INSUFFICIENT-EVIDENCE": insuff_d["outcome"],
        },
    }
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        f"bypass_ids={bypass_ids} kinds={sorted(kinds)} "
        f"clean_ok=True mutant_misses=True"
    )
    print("SUCCESS:TST-0311-probe2 bypass audit catches merge without gate decision")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
