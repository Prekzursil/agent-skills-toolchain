#!/usr/bin/env python3
"""Probe 1 (both-states): unbanded forward-looking claim is rejected; fully
banded output passes, so the lint is not an always-fail.

Planted hedge is the catalog phrase 'likely fine'.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from blueprints import all_blueprints, run_all  # noqa: E402
from contract import check_all, omissions_fail_distinctly  # noqa: E402
from lint import lint_document, lint_prose  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0247-probe1 {msg}")
    return 1


def main() -> int:
    bps = all_blueprints()
    if len(bps) != 4:
        return _fail(f"expected 4 blueprints, got {len(bps)}")
    contract_errs = check_all(bps)
    if any(contract_errs.values()):
        return _fail(f"contract {contract_errs}")
    tokens = omissions_fail_distinctly(bps[0])
    if any(v == "" for v in tokens.values()):
        return _fail(f"omission did not fail: {tokens}")
    if len(set(tokens.values())) < 6:
        return _fail(f"omission tokens not distinct: {tokens}")

    live = run_all()
    live_ok = {}
    for name, doc in live.items():
        report = lint_document(doc)
        live_ok[name] = report["ok"]
        if not report["ok"]:
            return _fail(f"live {name} lint blocked {report['findings']}")
        fwd = [c for c in doc["claims"] if c["register"] == "forward-looking"]
        if not fwd:
            return _fail(f"live {name} has no forward-looking claims")

    planted_path = HERE / "fixtures" / "planted-unbanded.json"
    banded_path = HERE / "fixtures" / "fully-banded.json"
    planted = json.loads(planted_path.read_text(encoding="utf-8"))
    banded = json.loads(banded_path.read_text(encoding="utf-8"))
    planted_report = lint_document(planted)
    banded_report = lint_document(banded)
    if planted_report["ok"]:
        return _fail("planted unbanded document was accepted")
    hedge_codes = {f["code"] for f in planted_report["findings"]}
    if "unbanded-hedge" not in hedge_codes and "unbanded-forward-claim" not in hedge_codes:
        return _fail(f"planted hedge not classified: {planted_report['findings']}")
    if not banded_report["ok"]:
        return _fail(f"fully banded fixture rejected: {banded_report['findings']}")

    # Mutate a live document: inject the catalog hedge. Must fire.
    mutant = copy.deepcopy(next(iter(live.values())))
    mutant["prose"] = (mutant.get("prose") or "") + " The Q3 launch is likely fine."
    mutant_report = lint_document(mutant)
    if mutant_report["ok"]:
        return _fail("live+hedge mutant was accepted (lint always-pass)")

    # Strip band from one live forward-looking claim. Must fire.
    stripped = copy.deepcopy(next(iter(live.values())))
    for c in stripped["claims"]:
        if c["register"] == "forward-looking":
            c.pop("confidence_band", None)
            c.pop("p_low", None)
            c.pop("p_high", None)
            break
    stripped_report = lint_document(stripped)
    if stripped_report["ok"]:
        return _fail("stripped-band mutant was accepted")

    # BLD-0031 control: calibrated 'likely (55-80%), measured at path:line'
    control = "likely (55-80%), measured at fixtures/market-landscape.json:1"
    control_findings = lint_prose(control)
    if control_findings:
        return _fail(f"calibrated-likely control flagged: {control_findings}")

    print(
        json.dumps(
            {
                "blueprints": sorted(live.keys()),
                "live_ok": live_ok,
                "planted_unbanded_rejected": True,
                "planted_codes": sorted(hedge_codes),
                "fully_banded_accepted": True,
                "live_plus_hedge_rejected": True,
                "stripped_band_rejected": True,
                "calibrated_likely_control_silent": True,
                "omission_tokens": tokens,
            },
            sort_keys=True,
        )
    )
    print(
        "fired_on_bad=True silent_on_good=True "
        "plant=likely-fine live_blueprints=4"
    )
    print("SUCCESS:IMP-0247-probe1 unbanded-forward-claim-rejected both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
