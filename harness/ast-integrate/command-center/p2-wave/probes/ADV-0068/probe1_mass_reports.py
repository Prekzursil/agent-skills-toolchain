#!/usr/bin/env python3
"""Probe 1: N distinct-identity reports against a legitimate fixture package.

Records whether any automatic yank, warning banner, or install block occurs
without human review. Also runs the single good-faith-report control (so an
unresponsive flow is not mistaken for a resistant one) and the unauthorized
false-advisory case against the same healthy fixture.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from probe_common import (  # noqa: E402
    LEGIT,
    N_REPORTS,
    dumps,
    fixture_engine,
    good_faith_control,
    report_identities,
)


def main() -> int:
    engine = fixture_engine()
    identities = report_identities(N_REPORTS)
    before = engine.install(LEGIT)
    reports = []
    for ident in identities:
        rec = engine.file_report(
            reporter_id=ident,
            package_id=LEGIT,
            reason="malware",
        )
        reports.append(
            {
                "report_id": rec.report_id,
                "reporter_id": rec.reporter_id,
                "status": rec.status,
                "automatic_enforcement": rec.automatic_enforcement,
            }
        )
    after = engine.auto_state(LEGIT)
    after_install = engine.install(LEGIT)
    distinct = {r["reporter_id"] for r in reports}

    false_adv = engine.file_advisory(
        signer_id="troll-consumer",
        signer_role="consumer",
        package_id=LEGIT,
        summary="this healthy fixture is malware (false)",
    )
    after_false = engine.install(LEGIT)

    control = good_faith_control(fixture_engine())

    auto_change = (
        after["yanked"]
        or after["warning_banner"]
        or after["install_blocked"]
        or any(r["automatic_enforcement"] for r in reports)
    )
    f1_refuted = (
        (not auto_change)
        and after_install.allowed
        and before.allowed
        and len(distinct) == N_REPORTS
        and all(r["status"] == "queued" for r in reports)
    )
    f2_refuted = (
        false_adv.get("accepted") is False
        and false_adv.get("reason") == "unauthorized-signer"
        and after_false.allowed is True
        and len(engine.open_advisories(LEGIT)) == 0
    )

    payload = {
        "probe": "probe1-mass-reports",
        "unit_id": "ADV-0068",
        "package_id": LEGIT,
        "fixture_only": True,
        "n_reports": len(reports),
        "distinct_identities": len(distinct),
        "identities": sorted(distinct),
        "auto_yank": after["yanked"],
        "warning_banner": after["warning_banner"],
        "install_blocked": after["install_blocked"],
        "install_after_mass": after_install.as_dict(),
        "false_advisory": {
            "accepted": false_adv.get("accepted"),
            "reason": false_adv.get("reason"),
            "healthy_still_installable": after_false.allowed,
        },
        "good_faith_control": control,
        "findings": {
            "F1-MASS-FALSE-REPORTS": "REFUTED" if f1_refuted else "CONFIRMED",
            "F2-FALSE-ADVISORY": "REFUTED" if f2_refuted else "CONFIRMED",
        },
        "pass": bool(f1_refuted and f2_refuted and control["pass"]),
    }
    print(dumps(payload))
    print(
        "mass n={0} distinct={1} auto_yank={2} banner={3} install_blocked={4} "
        "false_adv_accepted={5} good_faith={6}".format(
            payload["n_reports"],
            payload["distinct_identities"],
            payload["auto_yank"],
            payload["warning_banner"],
            payload["install_blocked"],
            false_adv.get("accepted"),
            control["pass"],
        )
    )
    if not payload["pass"]:
        print("FAILED:ADV-0068-probe1 mass-report / false-advisory measurement")
        return 1
    print("SUCCESS:ADV-0068-probe1 mass reports do not auto-enforce; false advisory refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
