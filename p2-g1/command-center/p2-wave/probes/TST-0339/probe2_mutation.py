#!/usr/bin/env python3
"""TST-0339 probe2: both-states mutation control on a scratch copy.

Baseline green; mutating the UNEXERCISED default (DEFAULT_MIN_BYTES
1024->512) keeps the suite green - the hole is real; mutating the EXERCISED
default (scale_by_factor factor 2->99) turns the suite red. The committed
fixtures are never touched.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROBE_DIR))
from mutate import apply, run_suite  # noqa: E402

FIXTURES = PROBE_DIR / "fixtures" / "estate"
RECEIPT = REPO / "command-center" / "receipts" / "TST-0339.json"
SENTINEL = "SUCCESS:TST-0339-probe2"

UNEX_OLD = "DEFAULT_MIN_BYTES = 1024"
UNEX_NEW = "DEFAULT_MIN_BYTES = 512"
EX_OLD = "def scale_by_factor(x, factor=2):"
EX_NEW = "def scale_by_factor(x, factor=99):"


def fail(msg):
    print("FAILED:TST-0339-probe2 " + msg)
    return 1


def main():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="tst0339-probe2-") as tmp:
        work = Path(tmp)

        base = apply(FIXTURES / "product.py", work / "product.py", "DEFAULT_MIN_BYTES = 1024", "DEFAULT_MIN_BYTES = 1024")
        shutil.copy(FIXTURES / "test_product.py", work / "test_product.py")
        checks = [("baseline-copy-ok", base["ok"] is True)]
        baseline = run_suite(work)
        checks.append(("baseline-green", baseline["exit_code"] == 0))

        m_unex = apply(FIXTURES / "product.py", work / "product.py", UNEX_OLD, UNEX_NEW)
        checks.append(("unex-mutation-applied", m_unex["ok"] is True))
        unex_run = run_suite(work)
        checks.append(("unexercised-default-change-stays-green", unex_run["exit_code"] == 0))

        shutil.copy(FIXTURES / "product.py", work / "product.py")
        m_ex2 = apply(work / "product.py", work / "product.py", EX_OLD, EX_NEW)
        checks.append(("ex-mutation-applied", m_ex2["ok"] is True))
        ex_run = run_suite(work)
        checks.append(("exercised-default-change-goes-red", ex_run["exit_code"] != 0))
        checks.append(("red-is-the-scale-test", any("test_scale" in line for line in ex_run["tail"])))

    both = receipt["both_states"]
    checks += [
        ("receipt-both-states-agrees",
            both["unexercised_default_change_stays_green"] is True
            and both["exercised_default_change_goes_red"] is True),
        ("receipt-anchors",
            both["planted_unexercised_anchor"].endswith("product.py:16")
            and both["planted_exercised_anchor"].endswith("product.py:26")),
    ]
    for name, ok in checks:
        print(("  ok " if ok else "  RED ") + name)
        if not ok:
            return fail("check " + name + " RED")
    print(json.dumps({
        "probe": "probe2-mutation", "unit_id": "TST-0339", "pass": True,
        "baseline_exit": 0,
        "unexercised_mutation_exit": unex_run["exit_code"],
        "exercised_mutation_exit": ex_run["exit_code"],
    }))
    print(SENTINEL + " unexercised default mutation stays green (hole proven); exercised default mutation goes red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
