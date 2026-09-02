#!/usr/bin/env python3
"""Probe 2: default exercised without size arg; mutation of the default goes RED."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import mutate as M  # noqa: E402
import suite as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0007.json"
UNIT = "TST-0007"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    live = S.run_suite(REPO)
    t = live["tests"][0]
    print(
        f"called_without_size_keys={t['called_without_size_keys']} "
        f"module_default={t['module_default']} "
        f"measured_threshold={t['measured_threshold']} "
        f"below={t['below_result']} at={t['at_result']} zero={t['zero_result']}"
    )
    if not live["green"]:
        for reason in t["reasons"]:
            print(" ", reason)
        return fail("live suite not green")
    if not t["called_without_size_keys"]:
        return fail("test still passes an explicit size argument")
    if t["id"] != "test_default_min_bytes_is_exercised_without_explicit_arg":
        return fail(f"unexpected test id {t['id']}")

    mut = M.flip_and_run(REPO)
    print(
        f"mutation operator={mut['operator']} live_green={mut['live_green']} "
        f"mutant_green={mut['mutant_green']} went_red={mut['went_red']}"
    )
    if mut["mutant_reasons"]:
        print("mutant_reasons " + " | ".join(mut["mutant_reasons"]))
    if not mut["went_red"]:
        return fail("flipping MIN_BYTES_DEFAULT did not turn the suite red")
    if mut["mutant_green"]:
        return fail("mutant suite stayed green (ledger 1024->512 shape)")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:TST-0007" not in text:
        return fail("sentinel absent")
    tests = doc.get("tests") or []
    ids = [x.get("id") for x in tests if isinstance(x, dict)]
    if "test_default_min_bytes_is_exercised_without_explicit_arg" not in ids:
        return fail("receipt missing default-exercise test id")
    nc = doc.get("negative_controls") or []
    fired = [
        c
        for c in nc
        if isinstance(c, dict)
        and c.get("fired_on_bad_state") is True
        and c.get("silent_on_good_state") is True
    ]
    if not fired:
        return fail("receipt missing armed mutation control")
    art_mut = (doc.get("mutation") or {})
    if art_mut.get("went_red") is not True:
        return fail("artifact mutation.went_red is not true")
    print("SUCCESS:TST-0007-probe2 default exercised; mutation went RED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
