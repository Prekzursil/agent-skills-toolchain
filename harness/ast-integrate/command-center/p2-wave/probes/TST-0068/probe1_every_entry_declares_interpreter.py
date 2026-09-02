#!/usr/bin/env python3
"""Probe 1: every script entry declares an interpreter (both-states).

Gold fixture: all 7 entries declare an interpreter (property holds).
Estate fixture: 4 shebang-reliant entries (property fails).
A detector that passed both would be vacuous.
Production hooks/_dispatch/manifest.json uses events.checks loaded in-process
by dispatch.py; a hooks[]-only parser that reports 0 on a present file is
green-not-live and fails this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/receipts/TST-0068.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0068-probe1 {msg}")
    return 1


def main() -> int:
    live = E.run_all()
    gold = live["gold"]
    estate = live["estate"]
    tests = live["tests"]

    if gold["vacuous"] or gold["count"] < 2:
        return fail(f"gold fixture vacuous count={gold['count']}")
    if gold["shebang_reliant_count"] != 0:
        return fail(f"gold shebang-reliant={gold['shebang_reliant_count']} want 0")
    if not gold["all_declare_interpreter"]:
        return fail("gold did not all declare interpreter")

    if estate["vacuous"] or estate["count"] != 7:
        return fail(f"estate count={estate['count']} want 7")
    if estate["shebang_reliant_count"] != 4:
        return fail(
            f"estate shebang-reliant={estate['shebang_reliant_count']} "
            f"ids={estate['shebang_reliant_ids']} want 4"
        )
    if estate["all_declare_interpreter"]:
        return fail("estate unexpectedly all-declare (detector silent on bad state)")

    related = live["related_tst0086"]
    if related.get("present") and related.get("shebang_reliant_count") != 0:
        return fail(
            f"TST-0086 manifest shebang-reliant={related.get('shebang_reliant_count')}"
        )

    prod = live["production"]
    if prod["any_present"] and prod["audit"]["vacuous"]:
        return fail(
            "production present but parser returned 0 entries (green-not-live)"
        )
    dispatch_checks = [
        e
        for e in (prod["audit"].get("entries") or [])
        if e.get("kind") == "dispatch-check"
    ]
    if dispatch_checks and any(e.get("relies_on_shebang") for e in dispatch_checks):
        return fail("dispatch-check scored as shebang (importlib inverted)")
    if (
        prod["any_present"]
        and prod["audit"]["shebang_reliant_count"]
        and prod["audit"]["all_declare_interpreter"]
    ):
        return fail("production census contradicts itself")
    if not prod["audit"]["vacuous"]:
        print("note: production catalog paths present and parsed")

    settings = live.get("settings_hooks") or {}
    if settings.get("present") and settings.get("vacuous"):
        return fail("settings.json present but 0 hook commands parsed")
    if settings.get("shebang_reliant_count"):
        return fail(
            f"settings spawn shebang-reliant="
            f"{settings.get('shebang_reliant_ids')}"
        )

    if not tests["test_every_script_entry_declares_an_interpreter"]:
        return fail("live test_every_script_entry_declares_an_interpreter is false")

    print(
        f"gold count={gold['count']} shebang_reliant={gold['shebang_reliant_count']} "
        f"all_declare={gold['all_declare_interpreter']}"
    )
    print(
        f"estate count={estate['count']} shebang_reliant={estate['shebang_reliant_count']} "
        f"ids={estate['shebang_reliant_ids']}"
    )
    print(
        f"production present={prod['any_present']} entries={prod['audit']['count']} "
        f"shebang_reliant={prod['audit']['shebang_reliant_count']} "
        f"vacuous={prod['audit']['vacuous']}"
    )
    print(
        f"settings present={settings.get('present')} entries={settings.get('count')} "
        f"shebang_reliant={settings.get('shebang_reliant_count')}"
    )

    if ART.is_file() and ART.stat().st_size > 0:
        doc = json.loads(ART.read_text(encoding="utf-8"))
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:TST-0068" not in text:
            return fail("artifact sentinel-absent")
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared:{st}")
        rec_tests = {
            t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)
        }
        row = rec_tests.get("test_every_script_entry_declares_an_interpreter")
        if not row or row.get("result") != "PASS":
            return fail("artifact missing PASS for interpreter-declaration test")
        ans = doc.get("answer") or {}
        if int(ans.get("shebang_reliant_count") or -1) != estate["shebang_reliant_count"]:
            return fail("artifact shebang_reliant_count drift vs live")
        rec_estate = (doc.get("estate") or {}).get("shebang_reliant_ids")
        if rec_estate is not None and list(rec_estate) != list(
            estate["shebang_reliant_ids"]
        ):
            return fail("artifact estate ids drift vs live")
        if int(ans.get("production_entries") or -1) != prod["audit"]["count"]:
            return fail("artifact production_entries drift vs live")
        if bool(ans.get("production_vacuous")) != bool(prod["audit"]["vacuous"]):
            return fail("artifact production_vacuous drift vs live")

    print("SUCCESS:TST-0068-probe1 every script entry declares an interpreter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
