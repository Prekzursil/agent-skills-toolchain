#!/usr/bin/env python3
"""Probe 2: backfill census as debt + cross-shell (pwsh7 vs Git Bash).

Census of the planted ledger reports the inadmissible fraction as debt
and does not retroactively admit incomplete rows. Cross-shell: the same
measurement under pwsh7 and Git Bash differs in `shell` and agrees on
every other mandatory field. Live analogue on this Linux host copies
/bin/bash to those names so the parent process actually differs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from bench.environment_record import (  # noqa: E402
    MANDATORY_FIELDS,
    census_paths,
    census_rows,
    compare_cross_shell,
    judge_environment,
    live_named_shell_pair,
    overlay_shell,
)
from fixtures import named_shell_pair, planted_rows, write_historical_jsonl  # noqa: E402

ART = REPO / "command-center/receipts/TST-0352.json"
SENTINEL = "SUCCESS:TST-0352"
LEDGER_LIVE = REPO / "command-center" / "bench" / "results"
RECEIPTS = REPO / "command-center" / "receipts"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0352-probe2 {msg}")
    return 1


def main() -> int:
    jsonl = write_historical_jsonl()
    planted = planted_rows()
    planted_census = census_rows(planted)
    expected_n = 1 + len(MANDATORY_FIELDS) + 1
    if planted_census["n"] != expected_n:
        return fail(f"planted n={planted_census['n']} expected {expected_n}")
    if planted_census["admitted"] != 1:
        return fail(f"planted admitted={planted_census['admitted']}")
    if planted_census["inadmissible"] != expected_n - 1:
        return fail(f"planted inadmissible={planted_census['inadmissible']}")
    if planted_census["fraction_inadmissible"] != (expected_n - 1) / expected_n:
        return fail(f"fraction={planted_census['fraction_inadmissible']}")
    if planted_census["debt_not_backfilled"] is not True:
        return fail("census backfilled debt")
    file_census = census_paths([jsonl])
    if file_census["inadmissible"] != planted_census["inadmissible"]:
        return fail("jsonl census drifted from planted_rows")

    live_ledger = census_paths([LEDGER_LIVE])
    receipt_paths = [
        p
        for p in sorted(RECEIPTS.glob("*.json"))
        if p.name != "TST-0352.json"
    ]
    receipt_census = census_paths(receipt_paths)
    if receipt_census["n"] and receipt_census["admitted"] != 0:
        # Historical receipts were not captured under this rule; admitting
        # any of them would be a retroactive accept.
        return fail("historical receipts retroactively admitted")

    git_bash, pwsh7 = named_shell_pair()
    named = compare_cross_shell(git_bash, pwsh7)
    if not named["shell_differs"]:
        return fail(f"named pair shell did not differ {named}")
    if not named["agree_elsewhere"]:
        return fail(f"named pair disagreed outside shell {named}")
    if not named["both_admitted"]:
        return fail("named pwsh7/git-bash pair not both admitted")
    if not named["comparable"]:
        return fail("named pair not comparable")
    if git_bash["shell"]["name"] == pwsh7["shell"]["name"]:
        return fail("shell names equal")

    # Drift control: OS mismatch must NOT look like a cross-shell pair.
    drifted = overlay_shell(git_bash, "pwsh7", pwsh7["shell"]["path"], pwsh7["shell"]["version"])
    drifted["os_build"] = dict(git_bash["os_build"], system="Windows")
    drift_cmp = compare_cross_shell(git_bash, drifted)
    if drift_cmp["agree_elsewhere"] or drift_cmp["comparable"]:
        return fail("OS drift treated as cross-shell agree")

    live = live_named_shell_pair()
    live_cmp = live["comparison"]
    if not live_cmp["shell_differs"]:
        return fail(f"live parent shells did not differ {live_cmp}")
    if not live_cmp["agree_elsewhere"]:
        return fail(f"live captures disagreed outside shell {live_cmp}")
    git_name = str((live["git_bash"].get("shell") or {}).get("name") or "")
    pwsh_name = str((live["pwsh7"].get("shell") or {}).get("name") or "")
    if "git-bash" not in git_name:
        return fail(f"live git-bash parent name={git_name!r}")
    if "pwsh7" not in pwsh_name:
        return fail(f"live pwsh7 parent name={pwsh_name!r}")

    live_git_v = judge_environment(live["git_bash"])
    live_pwsh_v = judge_environment(live["pwsh7"])
    # Live capture on this non-git worktree is expected to lack commit_sha.
    # That is inadmissible as evidence, which is the point of the gate.
    live_commit_status = {
        "git_bash_admitted": live_git_v["admitted"],
        "pwsh7_admitted": live_pwsh_v["admitted"],
        "git_bash_invalid": live_git_v["invalid_fields"],
        "pwsh7_invalid": live_pwsh_v["invalid_fields"],
    }

    if ART.is_file() and ART.stat().st_size > 0:
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if SENTINEL not in text:
            return fail("receipt sentinel-absent")
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared:{st}")
        debt = (doc.get("backfill_census") or {}).get("planted") or {}
        if debt.get("fraction_inadmissible") != planted_census["fraction_inadmissible"]:
            return fail("receipt census fraction drifted from live planted census")
        if doc.get("backfill_census", {}).get("debt_not_backfilled") is not True:
            return fail("receipt claims backfill/accept of historical rows")

    out = {
        "probe": "probe2-census-cross-shell",
        "unit_id": "TST-0352",
        "pass": True,
        "planted_census": {
            "n": planted_census["n"],
            "admitted": planted_census["admitted"],
            "inadmissible": planted_census["inadmissible"],
            "fraction_inadmissible": planted_census["fraction_inadmissible"],
            "debt_not_backfilled": True,
        },
        "live_ledger": {
            "present": LEDGER_LIVE.exists(),
            "n": live_ledger["n"],
            "inadmissible": live_ledger["inadmissible"],
            "fraction_inadmissible": live_ledger["fraction_inadmissible"],
            "paths_absent": live_ledger["paths_absent"],
        },
        "receipt_proxy_census": {
            "n": receipt_census["n"],
            "admitted": receipt_census["admitted"],
            "inadmissible": receipt_census["inadmissible"],
            "fraction_inadmissible": receipt_census["fraction_inadmissible"],
            "debt_not_backfilled": True,
        },
        "named_pwsh7_git_bash": named,
        "live_linux_standin": live_cmp,
        "live_commit_status": live_commit_status,
        "os_drift_not_comparable": (not drift_cmp["comparable"]),
    }
    print(json.dumps(out, sort_keys=True, default=str))
    frac = planted_census["fraction_inadmissible"]
    print(
        f"planted_debt={frac} receipt_proxy="
        f"{receipt_census['fraction_inadmissible']} "
        f"cross_shell={named['comparable']} live_shell_diff={live_cmp['shell_differs']}"
    )
    print("SUCCESS:TST-0352-probe2 census-as-debt and cross-shell pair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
