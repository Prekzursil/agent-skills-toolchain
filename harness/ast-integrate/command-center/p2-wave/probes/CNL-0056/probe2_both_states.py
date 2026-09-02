#!/usr/bin/env python3
"""Probe 2: both-states control + negative control, independently recounted.

Known-good fixture must be SILENT. Planted-bad fixture (SYN-03 removed) must
FIRE. The negative control is the planted-bad state: the check is meant to
reject a synthesis that dropped a canonical idea, and it must FIRE there.
A second walk (recount.py) must re-derive the same numbers from the fixtures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import ledger as L  # noqa: E402
import recount as R  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0056-idea-ledger-schema-and-per-participant-provenance.md"
)
GOOD = HERE / "fixtures/known-good.json"
BAD = HERE / "fixtures/planted-bad.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0056-probe2 artifact missing")
        return 1
    art = json.loads(ART.read_text(encoding="utf-8"))
    if art.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNL-0056-probe2 self-declared", art.get("state"))
        return 1

    good_doc = load(GOOD)
    bad_doc = load(BAD)
    good = L.check_disappearance(good_doc)
    bad = L.check_disappearance(bad_doc)
    g_ind = R.tabulate(good_doc)
    b_ind = R.tabulate(bad_doc)
    g_ok, g_why = R.numbers_agree(good, g_ind)
    b_ok, b_why = R.numbers_agree(bad, b_ind)

    silent_on_good = (
        good.get("silent") is True
        and good.get("fired") is False
        and good["signal_a"]["n_missing"] == 0
        and good["signal_b"]["n_missing"] == 0
        and g_ok
    )
    fired_on_bad = (
        bad.get("fired") is True
        and bad.get("silent") is False
        and "IDEA-0003" in (bad["signal_a"].get("missing") or [])
        and "mech.provenance.per-participant-origin"
        in (bad["signal_b"].get("missing") or [])
        and bad["signal_a"]["n_missing"] == 1
        and bad["signal_b"]["n_missing"] == 1
        and b_ok
    )
    negative = (
        "On the planted-bad fixture (synthesis node SYN-03 removed, ledger still "
        "holds IDEA-0003 with originator P-dave, supporter P-alice, fate DISSENTED), "
        f"the check FIRES. signal_a.missing={bad['signal_a'].get('missing')} "
        f"signal_b.missing={bad['signal_b'].get('missing')} fired={bad.get('fired')} "
        f"silent={bad.get('silent')}."
    )
    print(
        f"known-good silent={good.get('silent')} fired={good.get('fired')} "
        f"n_missing_ids={good['signal_a']['n_missing']} recount={g_why}"
    )
    print(
        f"planted-bad silent={bad.get('silent')} fired={bad.get('fired')} "
        f"missing_ids={bad['signal_a'].get('missing')} "
        f"missing_mechs={bad['signal_b'].get('missing')} recount={b_why}"
    )
    print(f"negative_control {negative}")
    print(f"fired_on_bad={fired_on_bad} silent_on_good={silent_on_good}")
    if not (silent_on_good and fired_on_bad):
        print("FAILED:CNL-0056-probe2 both-states did not discriminate")
        return 1
    recorded = art.get("negative_control") or {}
    if "FIRES" not in json.dumps(recorded) and "FIRE" not in json.dumps(art):
        print("FAILED:CNL-0056-probe2 artifact omits negative control")
        return 1
    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe2-both-states",
                "unit_id": "CNL-0056",
                "fired_on_bad": True,
                "silent_on_good": True,
                "independent_recount_agrees": True,
                "negative_control": negative,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNL-0056-probe2 both-states and negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
