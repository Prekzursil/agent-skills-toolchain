#!/usr/bin/env python3
"""Probe 2: independent capture oracle + overclaim mutant.

Does not import emit.py. Re-derives installed_client_reaches from capture
phrases and API fields, then checks the artifact. A mutant that claims npm
auto-uninstalls already-installed clients must fail.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from oracle import expected_rows, phrases_ok  # noqa: E402
from schema_local import domain  # noqa: E402

UNIT = "RES-0053"
ART = REPO / "command-center/research/RES-0053.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0053-probe2 {msg}")
    return 1


def npm_overclaim(row: dict) -> bool:
    """True when the row claims npm remotely uninstalls installed trees."""
    text = " ".join(
        str(row.get(k) or "")
        for k in ("installed_client", "registry_action", "reach_channel")
    ).lower()
    if row.get("installed_client_reaches") is True and row.get("registry") == "npm":
        return True
    needles = (
        "automatically uninstalled",
        "auto-uninstall",
        "remotely deletes node_modules",
        "pushes uninstall",
    )
    return any(n in text for n in needles)


def main() -> int:
    missing = phrases_ok()
    if missing:
        return fail(f"phrase-missing:{missing}")
    expect = expected_rows()
    for rid, spec in expect.items():
        if not spec.get("require"):
            return fail(f"api-precondition-failed:{rid}:{spec}")

    doc = json.loads(ART.read_text(encoding="utf-8"))
    body = domain(doc)
    rows = {
        r["registry"]: r
        for r in body.get("revocation_table") or []
        if isinstance(r, dict)
    }
    for rid, spec in expect.items():
        row = rows.get(rid)
        if row is None:
            return fail(f"artifact-missing-row:{rid}")
        got = row.get("installed_client_reaches")
        want = spec["installed_client_reaches"]
        if got is not want:
            return fail(f"{rid}:reaches got={got} want={want}")
        if spec["reach_channel"] != "none":
            if row.get("reach_channel") != spec["reach_channel"]:
                return fail(f"{rid}:channel {row.get('reach_channel')}")
        if npm_overclaim(row) and rid == "npm":
            return fail("npm-overclaim-in-live-artifact")

    reaches = [r.get("installed_client_reaches") for r in rows.values()]
    if True not in reaches or False not in reaches:
        return fail(f"no-contrast reaches={reaches}")

    incident = body.get("cited_incident") or {}
    ux = str(incident.get("what_installed_users_experienced") or "")
    if "npm audit" not in ux.lower() and "update" not in ux.lower():
        return fail("incident-missing-user-action")
    if "event-stream" not in str(incident.get("name") or ""):
        return fail("incident-not-event-stream")

    mutant = copy.deepcopy(doc)
    for row in domain(mutant)["revocation_table"]:
        if row.get("registry") == "npm":
            row["installed_client_reaches"] = True
            row["installed_client"] = (
                "npm automatically uninstalled already-installed copies"
            )
            row["reach_channel"] = "auto-uninstall"
    m_rows = {r["registry"]: r for r in domain(mutant)["revocation_table"]}
    if not npm_overclaim(m_rows["npm"]):
        return fail("overclaim-detector-inert")
    if m_rows["npm"]["installed_client_reaches"] == expect["npm"]["installed_client_reaches"]:
        return fail("overclaim-mutant-matches-oracle")

    print(
        "phrases_ok=True api_preconditions=True "
        f"reaches={[ (k, expect[k]['installed_client_reaches']) for k in expect ]} "
        "npm_overclaim_mutant_fires=True"
    )
    print("SUCCESS:RES-0053-probe2 capture-oracle overclaim-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
