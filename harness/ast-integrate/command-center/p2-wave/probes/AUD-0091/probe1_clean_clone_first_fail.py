#!/usr/bin/env python3
"""Probe 1: execute documented commands in a cache-free clone; record first fail.

Live worktree: git clone into redirected caches, then named README/RUNBOOK
census (commands are not executed on the live tree). Fixture both-states:
good sequence silent, bad sequence first-fail at exit 17. Does not implement
the in-place comparison (probe 2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

UID = "AUD-0091"
ART = REPO / "command-center/audit/AUD-0091-clean-room-clone-baseline.json"
OUT = HERE / "probe1-clean-clone-first-fail.raw.json"
SENTINEL = "SUCCESS:AUD-0091"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0091-probe1 {msg}")
    return 1


def main() -> int:
    wt = E.measure_worktree()
    good = E.run_documented_tree(E.FIXTURES / "good", clone_mode="copy")
    bad = E.run_documented_tree(E.FIXTURES / "bad", clone_mode="copy")

    if good.get("all_ok") is not True:
        return fail(f"good fixture not all_ok first_fail={good.get('first_fail')}")
    if good.get("cache", {}).get("ok") is not True:
        return fail("good fixture cache was not free")
    if len(good.get("commands") or []) < 3:
        return fail(f"good fixture extracted {good.get('commands')}")
    bf = bad.get("first_fail") or {}
    if bf.get("exit_code") != 17:
        return fail(f"bad fixture first_fail={bf}")
    if bad.get("n_ran") != 2:
        return fail(f"bad fixture should stop after step 2 n_ran={bad.get('n_ran')}")

    clone = wt["clone"]
    if clone.get("ok"):
        return fail("worktree git clone unexpectedly succeeded")
    if clone.get("exit_code") == 0:
        return fail("clone exit_code is 0")
    blob = (clone.get("output") or "").lower()
    if not any(
        token in blob
        for token in (
            "not a git repository",
            "does not appear to be a git repository",
            "does not exist",
            "git executable not found",
        )
    ):
        return fail(f"clone output not a clone-impossible signature: {blob[:300]}")
    if not wt["cache"]["ok"]:
        return fail("worktree cache redirect was not empty before clone")
    if wt["docs"]["present_count"] < 1:
        return fail(f"named docs unexpectedly absent: {wt['docs']}")
    if not (E.REPO / "README.md").is_file():
        return fail("README.md missing at repo root")
    if not (E.REPO / "command-center" / "RUNBOOK.md").is_file():
        return fail("command-center/RUNBOOK.md missing")
    if len(wt["docs"].get("commands") or []) < 5:
        return fail(f"too few extracted commands: {wt['docs'].get('commands')}")
    first = wt["clean"]["first_fail"] or {}
    if "git clone" not in str(first.get("command") or ""):
        return fail(f"worktree first fail was not clone: {first}")
    if wt["inplace"].get("skipped_execute") is not True:
        return fail("engine executed live documented commands; that is forbidden")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    rpt = doc.get("report") or {}
    if rpt.get("kind") != "audit-detector-control":
        return fail("report.kind is not audit-detector-control")
    art_clone = rpt.get("clone_transcript") or {}
    if int(art_clone.get("exit_code") or 0) == 0 or art_clone.get("ok") is True:
        return fail("artifact clone_transcript disagrees with live fail")
    art_first = rpt.get("first_failing_step") or {}
    if "git clone" not in str(art_first.get("command") or ""):
        return fail("artifact first_failing_step is not the clone")
    census = rpt.get("docs_census") or {}
    if int(census.get("present_count") or 0) < 1:
        return fail("artifact docs_census present_count drifted to 0")
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if (tests.get("AUD0091-clean-clone-first-fail") or {}).get("result") != "PASS":
        return fail("artifact test AUD0091-clean-clone-first-fail not PASS")

    raw = {
        "probe": "probe1-clean-clone-first-fail",
        "unit_id": UID,
        "pass": True,
        "worktree_clone_exit": clone["exit_code"],
        "worktree_first_fail_command": first.get("command"),
        "worktree_docs_present": wt["docs"]["present_count"],
        "worktree_n_commands": len(wt["docs"].get("commands") or []),
        "cache_free": wt["cache"]["ok"],
        "good_all_ok": good["all_ok"],
        "bad_first_exit": bf.get("exit_code"),
        "bad_n_ran": bad.get("n_ran"),
        "clone_output_tail": clone.get("output"),
        "live_execute_skipped": True,
    }
    OUT.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(raw, indent=1, sort_keys=True))
    print(
        f"clone_rc={clone['exit_code']} good_ok={good['all_ok']} "
        f"bad_rc={bf.get('exit_code')} cache_free={wt['cache']['ok']} "
        f"docs={wt['docs']['present_count']}"
    )
    print(
        "SUCCESS:AUD-0091-probe1 first-fail: worktree clone red; "
        "good fixture silent; bad fixture exit 17"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
