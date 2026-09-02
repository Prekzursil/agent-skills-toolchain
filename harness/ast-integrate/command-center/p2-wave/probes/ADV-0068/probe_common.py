"""Shared helpers for ADV-0068 named probes."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.moderation import (  # noqa: E402
    GATING_STATES,
    ModerationEngine,
    disputed_remains_gating,
    fixture_engine,
    install_calls_open_advisories,
    mutant_auto_delist,
    report_identities,
)

LEGIT = "fixture.legit-hello"
EVIL = "fixture.malware-beacon"
N_REPORTS = 20
MUTANT_THRESHOLD = 5
PROBE1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0068/probe1_mass_reports.py"
)
PROBE2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0068/probe2_unresolved_dispute.py"
)


def dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def good_faith_control(engine: ModerationEngine) -> dict[str, Any]:
    """A single good-faith report must produce the documented queued outcome."""
    rec = engine.file_report(
        reporter_id="good-faith-001",
        package_id=LEGIT,
        reason="spam",
    )
    after = engine.auto_state(LEGIT)
    return {
        "id": "CTRL-GOOD-FAITH-SINGLE-REPORT",
        "report_id": rec.report_id,
        "status": rec.status,
        "documented_outcome": rec.documented_outcome,
        "automatic_enforcement": rec.automatic_enforcement,
        "queued": rec.status == "queued",
        "no_auto_yank": after["yanked"] is False,
        "no_auto_banner": after["warning_banner"] is False,
        "install_still_allowed": after["install_blocked"] is False,
        "pass": (
            rec.status == "queued"
            and rec.automatic_enforcement is False
            and rec.documented_outcome == "report-accepted-pending-human-review"
            and after["yanked"] is False
            and after["warning_banner"] is False
            and after["install_blocked"] is False
        ),
    }


def mutant_control() -> dict[str, Any]:
    """NC-AUTO-DELIST-MUTANT: fires on mass reports, silent on one report."""
    bad = fixture_engine()
    for ident in report_identities(MUTANT_THRESHOLD):
        bad.file_report(reporter_id=ident, package_id=LEGIT, reason="malware")
    fired = mutant_auto_delist(bad, LEGIT, threshold=MUTANT_THRESHOLD)
    good = fixture_engine()
    good.file_report(reporter_id="solo-001", package_id=LEGIT, reason="malware")
    silent_fired = mutant_auto_delist(good, LEGIT, threshold=MUTANT_THRESHOLD)
    return {
        "id": "NC-AUTO-DELIST-MUTANT",
        "fired_on_bad_state": fired and bad.packages[LEGIT].yanked,
        "silent_on_good_state": (not silent_fired) and (not good.packages[LEGIT].yanked),
        "bad_n": len(bad.reports_for(LEGIT)),
        "good_n": len(good.reports_for(LEGIT)),
        "threshold": MUTANT_THRESHOLD,
        "pass": bool(fired and bad.packages[LEGIT].yanked and not silent_fired),
    }


__all__ = [
    "EVIL",
    "GATING_STATES",
    "HERE",
    "LEGIT",
    "MUTANT_THRESHOLD",
    "N_REPORTS",
    "PROBE1_CMD",
    "PROBE2_CMD",
    "REPO",
    "dumps",
    "disputed_remains_gating",
    "fixture_engine",
    "good_faith_control",
    "install_calls_open_advisories",
    "mutant_control",
    "report_identities",
]
