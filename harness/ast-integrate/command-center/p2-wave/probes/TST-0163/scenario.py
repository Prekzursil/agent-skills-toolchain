#!/usr/bin/env python3
"""Both-states + regression-seed scenarios for TST-0163."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from hash_spec import digest_bytes, digest_path
from launcher import FanOutLauncher, independent_digest

CAP_BEFORE = 8
CAP_AFTER = 32
N = 6
SPLIT = 3
FAMILY = "TST-0163-fanout-unit-spec"


def write_spec(path: Path, cap: int) -> str:
    doc = {
        "allowed_tools": ["Read", "Grep", "Bash", "Write"],
        "family": FAMILY,
        "phase": 10,
        "timeout_s": 30,
        "tool_call_cap": cap,
    }
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return digest_bytes(text.encode("utf-8"))


def run_cohort(*, detect: bool, edit: bool) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="tst0163-") as td:
        spec = Path(td) / "unit-spec.json"
        h_before = write_spec(spec, CAP_BEFORE)
        launcher = FanOutLauncher(spec, detect=detect)
        for i in range(SPLIT):
            launcher.dispatch(f"unit-{i:02d}")
        h_after = h_before
        if edit:
            h_after = write_spec(spec, CAP_AFTER)
        for i in range(SPLIT, N):
            launcher.dispatch(f"unit-{i:02d}")
        fanin = launcher.fan_in()
        independent_now, independent_pid = independent_digest(spec)
        saved_hashes = [
            digest_bytes(r["dispatch_spec_text"].encode("utf-8"))
            for r in launcher.records
        ]
        return {
            "detect": detect,
            "edit": edit,
            "h_before": h_before,
            "h_after": h_after,
            "independent_now": independent_now,
            "independent_pid": independent_pid,
            "saved_dispatch_hashes": saved_hashes,
            "in_process_now": digest_path(spec),
            **fanin,
        }


def test_unedited_reports_no_drift() -> dict[str, Any]:
    """Both-states good half: unedited run is silent."""
    row = run_cohort(detect=True, edit=False)
    ok = (
        row["result"] == "OK"
        and row["n_drifted"] == 0
        and row["contradictory_caps_live"] is False
        and row["caps_observed"] == [CAP_BEFORE]
        and row["named_hashes"]["dispatch"] == row["named_hashes"]["fanin"]
        and row["h_before"] == row["h_after"] == row["fanin_hash"]
        and row["pids_distinct"] is True
        and row["fanin_process"] == "independent-subprocess"
        and len(set(row["saved_dispatch_hashes"])) == 1
        and row["saved_dispatch_hashes"][0] == row["fanin_hash"]
    )
    return {"id": "test_unedited_reports_no_drift", "pass": ok, **_slim(row)}


def test_midrun_cap_edit_is_contract_drift() -> dict[str, Any]:
    """Regression seed: mid-run tool_call_cap edit is typed CONTRACT-DRIFT."""
    row = run_cohort(detect=True, edit=True)
    drifted = row["drifted_units"]
    named = row["named_hashes"]
    kinds = {d.get("kind") for d in drifted}
    ok = (
        row["result"] == "CONTRACT-DRIFT"
        and kinds == {"CONTRACT-DRIFT"}
        and row["n_drifted"] == SPLIT
        and row["contradictory_caps_live"] is True
        and row["caps_observed"] == [CAP_BEFORE, CAP_AFTER]
        and named["dispatch"] == row["h_before"]
        and named["fanin"] == row["h_after"]
        and named["dispatch"] != named["fanin"]
        and row["hashes_named_and_unequal"] is True
        and row["pids_distinct"] is True
        and row["independent_now"] == row["fanin_hash"] == row["h_after"]
        and all(d["dispatch_hash"] == row["h_before"] for d in drifted)
        and all(d["fanin_hash"] == row["h_after"] for d in drifted)
        and all(d["dispatch_tool_call_cap"] == CAP_BEFORE for d in drifted)
        and all(d["fanin_tool_call_cap"] == CAP_AFTER for d in drifted)
    )
    return {
        "id": "test_midrun_cap_edit_is_contract_drift",
        "pass": ok,
        "kinds": sorted(kinds),
        **_slim(row),
    }


def test_naive_last_write_wins_leaves_contradictory_caps() -> dict[str, Any]:
    """Negative: last-write-wins fan-in stays OK while both caps are live."""
    naive_edit = run_cohort(detect=False, edit=True)
    naive_clean = run_cohort(detect=False, edit=False)
    mutant_misses = (
        naive_edit["result"] == "OK"
        and naive_edit["n_drifted"] == 0
        and naive_edit["contradictory_caps_live"] is True
        and naive_edit["caps_observed"] == [CAP_BEFORE, CAP_AFTER]
        and naive_edit["n_compared"] == 1
        and naive_edit["fanin_process"] == "in-process-last-write-wins"
        and naive_edit["pids_distinct"] is False
    )
    silent_on_good = (
        naive_clean["result"] == "OK"
        and naive_clean["contradictory_caps_live"] is False
        and naive_clean["n_drifted"] == 0
    )
    ok = mutant_misses and silent_on_good
    return {
        "id": "test_naive_last_write_wins_leaves_contradictory_caps",
        "pass": ok,
        "mutant_misses": mutant_misses,
        "silent_on_good": silent_on_good,
        "naive_edit": _slim(naive_edit),
        "naive_clean": _slim(naive_clean),
    }


def _slim(row: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "result",
        "detect",
        "edit",
        "compare_mode",
        "fanin_hash",
        "fanin_process",
        "named_hashes",
        "hashes_named_and_unequal",
        "contradictory_caps_live",
        "caps_observed",
        "current_cap",
        "n_dispatched",
        "n_compared",
        "n_drifted",
        "h_before",
        "h_after",
        "independent_now",
        "pids_distinct",
        "launcher_pid",
        "fanin_hasher_pid",
        "drifted_units",
    )
    out = {k: row[k] for k in keep if k in row}
    recs = row.get("records") or []
    out["record_caps"] = [r.get("tool_call_cap") for r in recs]
    out["record_hashes"] = [r.get("dispatch_hash") for r in recs]
    return out


def run_all() -> dict[str, Any]:
    unedited = test_unedited_reports_no_drift()
    drift = test_midrun_cap_edit_is_contract_drift()
    naive = test_naive_last_write_wins_leaves_contradictory_caps()
    passed = unedited["pass"] and drift["pass"] and naive["pass"]
    return {
        "pass": passed,
        "cap_before": CAP_BEFORE,
        "cap_after": CAP_AFTER,
        "n": N,
        "split": SPLIT,
        "test_unedited_reports_no_drift": unedited,
        "test_midrun_cap_edit_is_contract_drift": drift,
        "test_naive_last_write_wins_leaves_contradictory_caps": naive,
    }


def main() -> int:
    out = run_all()
    print(json.dumps(out, sort_keys=True, default=str))
    if not out["pass"]:
        print("FAILED:TST-0163 scenario")
        return 1
    print("SUCCESS:TST-0163-scenario")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
