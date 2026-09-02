#!/usr/bin/env python3
"""Probe 1: three registry states + required client resolve tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from drill import PAYLOAD, run_drill  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:REL-0023-probe1 {msg}")
    return 1


def main() -> int:
    result = run_drill()
    by_state = {row["registry_state"]: row for row in result["registry_states"]}
    if set(by_state) != {"current", "deprecated", "revoked"}:
        return fail(f"missing states {sorted(by_state)}")

    current = by_state["current"]
    if current["observed_action"] != "STAY_CURRENT":
        return fail(f"current next-resolve {current['observed_action']}")
    if current.get("warning"):
        return fail("current state emitted a warning")

    deprecated = by_state["deprecated"]
    if deprecated["observed_action"] != "WARN_STAY":
        return fail(f"deprecated next-resolve {deprecated['observed_action']}")
    warning = deprecated.get("warning") or ""
    if "DEPRECATED" not in warning or "1.2.0" not in warning:
        return fail(f"deprecated warning missing successor: {warning!r}")
    dep_install = deprecated.get("deprecated_version_install") or {}
    if dep_install.get("action") != "MOVE_OK":
        return fail(f"deprecated 1.1.0 did not install: {dep_install}")
    if not dep_install.get("warning") or "DEPRECATED" not in dep_install["warning"]:
        return fail("deprecated 1.1.0 install had no visible warning")
    if dep_install.get("executed") != PAYLOAD["1.1.0"]:
        return fail("deprecated install did not execute 1.1.0 bytes")
    fresh_dep = deprecated["fresh_install"]
    if fresh_dep["action"] != "INSTALL_OK":
        return fail(f"deprecated fresh install {fresh_dep['action']}")
    if fresh_dep["version"] != "1.2.0":
        return fail(f"fresh install under deprecated 1.1.0 picked {fresh_dep['version']}")
    if fresh_dep.get("warning"):
        return fail("fresh install of current 1.2.0 warned while only 1.1.0 is deprecated")

    # Explicit: a deprecated-but-not-revoked version still installs with a warning.
    # Re-run that exact case via the observation's registry is already captured
    # for 1.1.0 at next-resolve. Confirm a targeted move to 1.1.0 while deprecated
    # is INSTALL/MOVE with warning (done as WARN_STAY for the pin).
    if "successor=harness.canary@1.2.0" not in warning:
        return fail("deprecated warning did not name the successor")

    revoked = by_state["revoked"]
    if revoked["observed_action"] != "KEEP_RUNNING_UNAWARE":
        return fail(f"revoked already-installed {revoked['observed_action']}")
    refuse = result["refuse_move"]
    if refuse["action"] != "REFUSE_MOVE" or refuse.get("offered") != "1.1.0":
        return fail(f"installed client did not refuse move to revoked: {refuse}")
    fresh = result["fresh_revoked"]
    if fresh["action"] != "INSTALL_OK":
        return fail(f"fresh after revoke {fresh}")
    if fresh["version"] == "1.1.0":
        return fail("fresh install resolved the revoked version")
    if fresh["version"] != "1.2.0":
        return fail(f"fresh install picked {fresh['version']}")
    if fresh.get("executed") == PAYLOAD["1.1.0"]:
        return fail("fresh install executed withdrawn bytes")
    if result.get("successor_missing") != "RegistryError":
        return fail(f"missing-successor deprecation {result.get('successor_missing')}")

    iso = result["isolation"]
    if not iso.get("isolated") or not iso.get("owner_home_untouched"):
        return fail(f"isolation {iso}")

    print(
        json.dumps(
            {
                "probe": "probe1-client-resolve",
                "unit_id": "REL-0023",
                "pass": True,
                "current": current["observed_action"],
                "deprecated": deprecated["observed_action"],
                "revoked_already_installed": revoked["observed_action"],
                "refuse_move": refuse["action"],
                "fresh_version": fresh["version"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:REL-0023-probe1 client resolve across current/deprecated/revoked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
