#!/usr/bin/env python3
"""Probe 2: dispute on a known-malicious fixture; measure unresolved enforcement.

Mechanically different from probe 1 (which floods a healthy package with reports).
Here a valid signed advisory already gates install. Filing a publisher dispute
must not suspend that gate while the dispute is open, and must not record a
silent owner override. Also records the auto-delist mutant negative control and
the static proof that install() calls open_advisories() and that 'disputed'
stays in GATING_STATES.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from probe_common import (  # noqa: E402
    EVIL,
    GATING_STATES,
    dumps,
    disputed_remains_gating,
    fixture_engine,
    install_calls_open_advisories,
    mutant_control,
)


def main() -> int:
    engine = fixture_engine()
    filed = engine.file_advisory(
        signer_id="mod-01",
        signer_role="moderator",
        package_id=EVIL,
        summary="fixture.malware-beacon ships a known beacon",
    )
    if not filed.get("accepted"):
        print("FAILED:ADV-0068-probe2 authorized advisory refused")
        return 1
    advisory = filed["advisory"]
    before = engine.install(EVIL)
    open_before = [a.advisory_id for a in engine.open_advisories(EVIL)]

    dispute = engine.file_dispute(filer_id="pub-evil", advisory_id=advisory.advisory_id)
    after = engine.install(EVIL)
    open_after = engine.open_advisories(EVIL)
    open_ids = [a.advisory_id for a in open_after]
    disputed_states = [a.state for a in open_after]

    static_install = install_calls_open_advisories()
    static_gating = disputed_remains_gating()
    nc = mutant_control()

    still_blocked = after.allowed is False
    still_listed = advisory.advisory_id in open_ids
    no_override = after.override_recorded is False
    f3_refuted = (
        before.allowed is False
        and still_blocked
        and still_listed
        and "disputed" in disputed_states
        and no_override
        and dispute.state == "open"
        and "disputed" in GATING_STATES
        and static_install
        and static_gating
    )

    payload = {
        "probe": "probe2-unresolved-dispute",
        "unit_id": "ADV-0068",
        "package_id": EVIL,
        "fixture_only": True,
        "advisory_id": advisory.advisory_id,
        "advisory_state_after_dispute": advisory.state,
        "dispute_id": dispute.dispute_id,
        "dispute_state": dispute.state,
        "install_before_dispute": before.as_dict(),
        "install_after_dispute": after.as_dict(),
        "open_advisories_before": open_before,
        "open_advisories_after": open_ids,
        "disputed_still_gating": still_listed,
        "override_recorded": after.override_recorded,
        "install_calls_open_advisories": static_install,
        "disputed_in_gating_states": static_gating,
        "negative_control": nc,
        "findings": {
            "F3-UNRESOLVED-DISPUTE": "REFUTED" if f3_refuted else "CONFIRMED",
        },
        "pass": bool(f3_refuted and nc["pass"]),
    }
    print(dumps(payload))
    print(
        "blocked_before={0} blocked_after={1} disputed_gating={2} "
        "override={3} mutant_bad={4} mutant_good_silent={5}".format(
            before.allowed is False,
            still_blocked,
            still_listed,
            after.override_recorded,
            nc["fired_on_bad_state"],
            nc["silent_on_good_state"],
        )
    )
    if not payload["pass"]:
        print("FAILED:ADV-0068-probe2 unresolved-dispute measurement")
        return 1
    print("SUCCESS:ADV-0068-probe2 dispute does not suspend enforcement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
