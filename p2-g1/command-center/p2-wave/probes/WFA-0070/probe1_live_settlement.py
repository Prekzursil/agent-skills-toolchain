#!/usr/bin/env python3
"""Named probe 1: re-run live locator settlement and check the artifact.

The catalog n=44 is not used as a member-ID list. Recovered IDs come from
the registry file when present; otherwise 44 slots stay UNKNOWN with the
blocker named.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import settle as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0070-unknown-needs-probe-settlement.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0070-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    if doc.get("unit_id") != "WFA-0070":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0070" not in text:
        return fail("sentinel absent")

    live = S.settle_live(REPO)
    if live["recovered_n"] != doc.get("recovered_unknown_n"):
        return fail(
            f"recovered mismatch live={live['recovered_n']} "
            f"art={doc.get('recovered_unknown_n')}"
        )
    if live["remaining_unknown_n"] != doc.get("remaining_unknown_n"):
        return fail(
            f"remaining mismatch live={live['remaining_unknown_n']} "
            f"art={doc.get('remaining_unknown_n')}"
        )
    if live["settled_n"] != doc.get("settled_n"):
        return fail(
            f"settled_n mismatch live={live['settled_n']} art={doc.get('settled_n')}"
        )
    if live["source"] != doc.get("live_source"):
        return fail(f"source mismatch live={live['source']} art={doc.get('live_source')}")
    if len(doc.get("candidates") or []) != live["settled_n"]:
        return fail("artifact candidate count != settled_n")
    if live["settled_n"] < S.CATALOG_CLAIMED_N and live["source"] == "catalog-claimed-slots":
        return fail("slot settlement shorter than catalog-claimed 44")

    for i, row in enumerate(doc.get("candidates") or []):
        probe = row.get("probe") or {}
        if not probe.get("command") or not probe.get("verbatim"):
            return fail(f"row {i} missing command/verbatim")
        if not row.get("both_states"):
            return fail(f"row {i} missing both_states")
        if row.get("resolved_by_default") is True:
            return fail(f"row {i} resolved_by_default")
        if row.get("read_only") is not True:
            return fail(f"row {i} not read_only")
        if row.get("estate_writes"):
            return fail(f"row {i} estate_writes nonempty")
        if (probe.get("signal") == "unconstructable") and row.get(
            "implied_disposition"
        ) != S.UNKNOWN:
            return fail(f"row {i} unconstructable was resolved")

    if live["source"] == "catalog-claimed-slots":
        if live["remaining_unknown_n"] != S.CATALOG_CLAIMED_N:
            return fail("registry miss must leave 44 UNKNOWN, not zero-as-settled")
        blockers = {r.get("blocker") for r in (doc.get("candidates") or [])}
        if blockers != {"authoritative-registry-absent-on-this-worktree"}:
            return fail(f"unexpected blockers {blockers}")

    inv = doc.get("invariants") or {}
    if not inv.get("every_row_has_probe_command_and_verbatim"):
        return fail("invariants.probe missing")
    if not inv.get("every_row_carries_both_states"):
        return fail("invariants.both_states missing")
    if not inv.get("no_default_resolution"):
        return fail("invariants.no_default_resolution false")
    if not inv.get("read_only"):
        return fail("invariants.read_only false")

    payload = {
        "probe": "probe1-live-settlement",
        "unit_id": "WFA-0070",
        "pass": True,
        "recovered_n": live["recovered_n"],
        "remaining_unknown_n": live["remaining_unknown_n"],
        "settled_n": live["settled_n"],
        "source": live["source"],
        "read_only": True,
        "no_default_resolution": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"recovered={live['recovered_n']} remaining={live['remaining_unknown_n']} "
        f"source={live['source']} rows={live['settled_n']}"
    )
    print("SUCCESS:WFA-0070-probe1 live named-probe settlement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
