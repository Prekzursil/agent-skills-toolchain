"""TST-0303 expiry unit tests (mirrors the probe checks as pytest)."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.expire import cite_as_current, gate_accepts  # noqa: E402
from bench.ttl import ttl_for  # noqa: E402

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


@dataclass
class Result:
    result_id: str
    case_id: str
    verdict: str
    observed_class: str
    captured_at: datetime


def test_ttl_table_classes():
    assert ttl_for("hermetic") is None
    assert ttl_for("advisory-db") == 86400
    assert ttl_for("model-endpoint") == 21600
    assert ttl_for("unknown-live") == 3600


def test_expired_cannot_gate():
    r = Result("x", "advisory-nvd", "PASS", "advisory-db",
               NOW - timedelta(seconds=86401))
    assert gate_accepts(r, NOW)["accepted"] is False
    assert cite_as_current(r, NOW).status == "EXPIRED-NOT-CHECKED"


def test_fresh_and_hermetic_still_current():
    fresh = Result("y", "advisory-nvd", "PASS", "advisory-db",
                   NOW - timedelta(seconds=3600))
    assert gate_accepts(fresh, NOW)["accepted"] is True
    old = Result("z", "hermetic-digest", "PASS", "hermetic",
                 NOW - timedelta(days=3650))
    assert gate_accepts(old, NOW)["accepted"] is True
