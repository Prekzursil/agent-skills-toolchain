"""Tests for command-center/ssot/capability_score.py (no network, no clock).

Every test passes ``now`` explicitly so the arithmetic is reproducible, and the
sidecar is always a ``tmp_path`` file. The one import-time side effect of the module
(loading ``atomic_write_json`` by path from ``.agents/scripts/mcp_control_plane.py``)
is exercised against a temp module so the fallback branches are proven, not assumed.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

SSOT = Path(__file__).resolve().parents[1]
if str(SSOT) not in sys.path:
    sys.path.insert(0, str(SSOT))

import capability_score as cs  # noqa: E402

NOW = "2026-09-02T03:30:00+00:00"
EP = "ep"


def at(seconds: int = 0, **delta: int) -> str:
    """``NOW`` shifted by ``seconds`` (and any ``timedelta`` keyword)."""
    base = datetime.fromisoformat(NOW) + timedelta(seconds=seconds, **delta)
    return base.isoformat(timespec="seconds")


def good_row(**extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": EP,
        "ok": True,
        "latency_ms": 100,
        "claimed": ["wire.completions"],
        "observed": {"wire.completions": True},
        "digest": "unchanged",
        "scan": "clean",
        "claim_agreement": True,
    }
    row.update(extra)
    return row


def bad_row(**extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"id": EP, "ok": False}
    row.update(extra)
    return row


def fold(rows: list[tuple[str, dict[str, Any]]], **policy: int) -> dict[str, Any]:
    """Fold ``(now, row)`` pairs into one entry, in order."""
    entry: dict[str, Any] | None = None
    for now, row in rows:
        entry = cs.update_entry(entry, cs.validate_row(row), now=now, **policy)
    assert entry is not None
    return entry


def entry_for(state: str, **extra: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "score": 100,
        "components": dict.fromkeys(cs.COMPONENTS, 0),
        "state": state,
        "consecutive_good": 0,
        "failures": [],
        "last_probe": {},
    }
    entry.update(extra)
    return entry


# ---------------------------------------------------------------------------
# Utilities and the atomic writer
# ---------------------------------------------------------------------------
def test_parse_iso_reads_naive_as_utc_and_rejects_junk() -> None:
    assert cs.parse_iso("2026-09-02T03:30:00").tzinfo is timezone.utc
    assert cs.parse_iso(NOW) == datetime(2026, 9, 2, 3, 30, tzinfo=timezone.utc)
    with pytest.raises(cs.CapabilityScoreError, match="bad timestamp"):
        cs.parse_iso("yesterday")
    with pytest.raises(cs.CapabilityScoreError, match="bad timestamp"):
        cs.parse_iso(None)


def test_local_atomic_writer_creates_parents_and_leaves_no_temp_on_failure(
    tmp_path: Path,
) -> None:
    target = tmp_path / "nested" / "scores.json"
    cs._local_atomic_write_json(target, {"a": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
    assert target.read_bytes().endswith(b"}\n")

    with pytest.raises(TypeError):
        cs._local_atomic_write_json(target, {"bad": object()})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
    assert [p.name for p in target.parent.iterdir()] == ["scores.json"]


def test_load_atomic_writer_prefers_the_control_plane_and_falls_back(
    tmp_path: Path,
) -> None:
    assert cs.load_atomic_writer(tmp_path / "absent.py") is cs._local_atomic_write_json
    not_python = tmp_path / "pyrightconfig.json"
    not_python.write_text("{}", encoding="utf-8")
    assert cs.load_atomic_writer(not_python) is cs._local_atomic_write_json

    module = tmp_path / "fake_control_plane.py"
    module.write_text(
        "def atomic_write_json(path, payload):\n    return ('fake', path, payload)\n",
        encoding="utf-8",
    )
    writer = cs.load_atomic_writer(module)
    assert writer(Path("x"), {}) == ("fake", Path("x"), {})

    real = cs.load_atomic_writer()
    assert real is not cs._local_atomic_write_json
    assert real.__name__ == "atomic_write_json"
    real(tmp_path / "via-control-plane.json", {"ok": True})
    assert json.loads((tmp_path / "via-control-plane.json").read_text()) == {"ok": True}


# ---------------------------------------------------------------------------
# Closed schemas
# ---------------------------------------------------------------------------
def test_check_keys_rejects_non_objects_unknown_and_missing() -> None:
    with pytest.raises(cs.CapabilityScoreError, match="must be an object"):
        cs._check_keys([], ("a",), ("a",), "thing")
    with pytest.raises(cs.CapabilityScoreError, match="unknown key"):
        cs._check_keys({"a": 1, "zz": 2}, ("a",), (), "thing")
    with pytest.raises(cs.CapabilityScoreError, match="lacks key"):
        cs._check_keys({}, ("a",), ("a",), "thing")
    assert cs._check_keys({"a": 1}, ("a",), ("a",), "thing") == {"a": 1}


def test_string_list() -> None:
    assert cs._string_list(["a"], "x") == ["a"]
    with pytest.raises(cs.CapabilityScoreError, match="list of strings"):
        cs._string_list("a", "x")
    with pytest.raises(cs.CapabilityScoreError, match="list of strings"):
        cs._string_list(["a", 1], "x")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"typo": 1}, "unknown key"),
        ({"components": {"availability": 1}}, "components lacks"),
        ({"last_probe": {"nope": 1}}, "last_probe has unknown"),
        ({"state": "zombie"}, "not a known state"),
        ({"score": 1.5}, "score must be an integer"),
        ({"score": True}, "score must be an integer"),
        ({"consecutive_good": "2"}, "consecutive_good must be an integer"),
        ({"failures": [1]}, "failures must be a list"),
        ({"retired_by": ""}, "retired_by must be a non-empty"),
        ({"retired_by": 7}, "retired_by must be a non-empty"),
        ({"state": "retired"}, "retired without retired_by"),
    ],
)
def test_validate_entry_rejects(mutation: dict[str, Any], message: str) -> None:
    with pytest.raises(cs.CapabilityScoreError, match=message):
        cs.validate_entry(EP, {**entry_for("live"), **mutation})


def test_validate_entry_accepts_retired_with_a_human_retired_by() -> None:
    entry = entry_for("retired", retired_by="owner 2026-09-01")
    assert cs.validate_entry(EP, entry) is entry


def test_validate_state_rejects_top_level_defects() -> None:
    with pytest.raises(cs.CapabilityScoreError, match="state lacks"):
        cs.validate_state({"schemaVersion": 1})
    with pytest.raises(cs.CapabilityScoreError, match="schemaVersion must be 1"):
        cs.validate_state({"schemaVersion": 2, "updated_at": NOW, "endpoints": {}})
    with pytest.raises(cs.CapabilityScoreError, match="endpoints must be an object"):
        cs.validate_state({"schemaVersion": 1, "updated_at": NOW, "endpoints": []})
    with pytest.raises(cs.CapabilityScoreError, match="unknown key"):
        cs.validate_state({**cs.empty_state(NOW), "extra": 1})
    good = {"schemaVersion": 1, "updated_at": NOW, "endpoints": {EP: entry_for("live")}}
    assert cs.validate_state(good) is good


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ({"id": EP, "ok": True, "bogus": 1}, "unknown key"),
        ({"id": EP}, "lacks key"),
        ({"id": EP, "ok": "yes"}, "row.ok has the wrong type"),
        ({"id": "  ", "ok": True}, "id must be non-empty"),
        ({"id": EP, "ok": True, "claimed": [1]}, "claimed must be a list of strings"),
        ({"id": EP, "ok": True, "digest": "drifted"}, "row.digest must be one of"),
        ({"id": EP, "ok": True, "scan": "loud"}, "row.scan must be one of"),
    ],
)
def test_validate_row_rejects(row: dict[str, Any], message: str) -> None:
    with pytest.raises(cs.CapabilityScoreError, match=message):
        cs.validate_row(row)


def test_validate_row_accepts_minimal_and_full_rows() -> None:
    assert cs.validate_row({"id": EP, "ok": False}) == {"id": EP, "ok": False}
    full = good_row(
        availability=0.5,
        baseline_latency_ms=90,
        reviewed=True,
        deprecation_signal="expired",
        last_success_at=NOW,
    )
    assert cs.validate_row(full) is full


def test_load_state_missing_invalid_and_valid(tmp_path: Path) -> None:
    assert cs.load_state(tmp_path / "none.json", now=NOW) == cs.empty_state(NOW)
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json", encoding="utf-8")
    with pytest.raises(cs.CapabilityScoreError, match="not valid JSON"):
        cs.load_state(corrupt, now=NOW)
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"schemaVersion": 1}), encoding="utf-8")
    with pytest.raises(cs.CapabilityScoreError, match="state lacks"):
        cs.load_state(wrong, now=NOW)
    valid = tmp_path / "valid.json"
    valid.write_text(json.dumps(cs.empty_state(NOW)), encoding="utf-8")
    assert cs.load_state(valid, now=NOW) == cs.empty_state(NOW)


# ---------------------------------------------------------------------------
# Score components: table-driven
# ---------------------------------------------------------------------------
def expected(**parts: int) -> dict[str, int]:
    base = {
        "availability": 0,
        "capability": 10,
        "latency": 0,
        "freshness": 0,
        "security": 10,
        "claim_agreement": 5,
    }
    base.update(parts)
    return base


@pytest.mark.parametrize(
    ("row", "parts"),
    [
        (
            good_row(baseline_latency_ms=100, last_success_at=NOW),
            expected(availability=40, capability=20, latency=15, freshness=10),
        ),
        (bad_row(), expected()),
        (bad_row(availability=0.5), expected(availability=20)),
        (bad_row(availability=1.5), expected(availability=40)),
        (bad_row(availability=-0.2), expected()),
        (
            bad_row(
                claimed=["a", "b", "c"], observed={"a": True, "b": False, "z": True}
            ),
            expected(capability=10),
        ),
        (bad_row(claimed=["a"], observed={"a": False}), expected(capability=0)),
        (bad_row(claimed=["a"], observed={}), expected(capability=10)),
        (bad_row(latency_ms=50), expected(latency=15)),
        (bad_row(latency_ms=50, baseline_latency_ms=0), expected(latency=15)),
        (bad_row(latency_ms=150, baseline_latency_ms=100), expected(latency=15)),
        (bad_row(latency_ms=200, baseline_latency_ms=100), expected(latency=10)),
        (bad_row(latency_ms=300, baseline_latency_ms=100), expected(latency=0)),
        (bad_row(latency_ms=900, baseline_latency_ms=100), expected(latency=0)),
        (bad_row(last_success_at=at(hours=-12)), expected(freshness=10)),
        (bad_row(last_success_at=at(days=-3)), expected(freshness=5)),
        (bad_row(last_success_at=at(days=-8)), expected(freshness=0)),
        (bad_row(last_success_at="2026-09-02T03:00:00"), expected(freshness=10)),
        (bad_row(scan="findings", digest="unchanged"), expected(security=0)),
        (bad_row(digest="changed"), expected(security=0)),
        (bad_row(digest="changed", reviewed=True), expected(security=5)),
        (bad_row(digest="pinned", scan="skipped"), expected(security=10)),
        (bad_row(claim_agreement=False), expected(claim_agreement=0)),
        (bad_row(claim_agreement=None), expected(claim_agreement=5)),
    ],
)
def test_component_table(row: dict[str, Any], parts: dict[str, int]) -> None:
    assert cs.components(cs.validate_row(row), now=NOW) == parts
    assert cs.score(row, now=NOW) == sum(parts.values())
    assert cs.WEIGHTS == {
        "availability": 40,
        "capability": 20,
        "latency": 15,
        "freshness": 10,
        "security": 10,
        "claim_agreement": 5,
    }
    assert sum(cs.WEIGHTS.values()) == 100


def test_components_default_now_is_the_wall_clock() -> None:
    fresh = cs.components(bad_row(last_success_at=cs.utc_now_iso()))
    assert fresh["freshness"] == 10
    assert cs.score(bad_row()) == 25


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------
def test_prune_failures_forgets_anything_outside_the_window() -> None:
    kept = cs.prune_failures([at(-700), at(-600), at(-1)], at(0), 600)
    assert kept == [at(-600), at(-1)]


@pytest.mark.parametrize(
    ("previous", "kwargs", "state"),
    [
        (None, {"retired_by": "owner"}, "retired"),
        ("live", {"failures_in_window": 3}, "quarantined"),
        ("live", {"deprecation_signal": "expired"}, "deprecation-candidate"),
        (None, {}, "live"),
        ("live", {"total": 59}, "degraded"),
        ("live", {"claim_points": 0}, "degraded"),
        ("degraded", {"consecutive_good": 1}, "degraded"),
        ("degraded", {"consecutive_good": 2}, "live"),
        ("quarantined", {"consecutive_good": 0}, "degraded"),
        ("deprecation-candidate", {"consecutive_good": 2}, "live"),
    ],
)
def test_decide_state_precedence(
    previous: str | None, kwargs: dict[str, Any], state: str
) -> None:
    defaults: dict[str, Any] = {
        "retired_by": None,
        "deprecation_signal": None,
        "failures_in_window": 0,
        "threshold": 3,
        "total": 100,
        "claim_points": 5,
        "consecutive_good": 0,
    }
    defaults.update(kwargs)
    assert cs.decide_state(previous, **defaults) == state


def test_hysteresis_two_good_runs_leave_degraded() -> None:
    first = fold([(at(0), good_row())])
    assert (first["state"], first["score"], first["consecutive_good"]) == (
        "live",
        100,
        1,
    )
    assert first["last_probe"] == {
        "at": at(0),
        "ok": True,
        "latency_ms": 100,
        "baseline_latency_ms": 100,
        "last_success_at": at(0),
    }
    assert "retired_by" not in first

    dropped = cs.update_entry(first, bad_row(), now=at(60))
    assert dropped["state"] == "degraded"
    assert dropped["score"] == 35
    assert dropped["consecutive_good"] == 0
    assert dropped["failures"] == [at(60)]
    assert dropped["last_probe"]["last_success_at"] == at(0)
    assert dropped["last_probe"]["baseline_latency_ms"] == 100

    once = cs.update_entry(dropped, good_row(latency_ms=200), now=at(120))
    assert (once["state"], once["consecutive_good"]) == ("degraded", 1)
    assert once["last_probe"]["baseline_latency_ms"] == 120

    twice = cs.update_entry(once, good_row(), now=at(180))
    assert (twice["state"], twice["consecutive_good"]) == ("live", 2)


def test_hysteresis_claim_disagreement_degrades_and_blocks_recovery() -> None:
    live = fold([(at(0), good_row())])
    disagree = cs.update_entry(live, good_row(claim_agreement=False), now=at(60))
    assert disagree["state"] == "degraded"
    assert disagree["score"] == 95
    assert disagree["consecutive_good"] == 0

    still = cs.update_entry(disagree, good_row(claim_agreement=False), now=at(120))
    assert (still["state"], still["consecutive_good"]) == ("degraded", 0)

    back = fold(
        [(at(180), good_row()), (at(240), good_row())],
    )
    recovered = cs.update_entry(
        cs.update_entry(still, good_row(), now=at(180)), good_row(), now=at(240)
    )
    assert recovered["state"] == "live"
    assert back["state"] == "live"


def test_quarantine_needs_three_failures_inside_the_window() -> None:
    quarantined = fold([(at(0), bad_row()), (at(100), bad_row()), (at(200), bad_row())])
    assert quarantined["state"] == "quarantined"
    assert quarantined["failures"] == [at(0), at(100), at(200)]

    spread = fold([(at(0), bad_row()), (at(700), bad_row()), (at(800), bad_row())])
    assert spread["state"] == "degraded"
    assert spread["failures"] == [at(700), at(800)]

    strict = fold([(at(0), bad_row()), (at(100), bad_row())], threshold=2)
    assert strict["state"] == "quarantined"


def test_quarantine_holds_until_the_window_passes_then_hysteresis_applies() -> None:
    quarantined = fold([(at(0), bad_row()), (at(100), bad_row()), (at(200), bad_row())])
    inside = cs.update_entry(quarantined, good_row(), now=at(300))
    assert (inside["state"], inside["consecutive_good"]) == ("quarantined", 1)
    outside = cs.update_entry(inside, good_row(), now=at(900))
    assert outside["failures"] == []
    assert (outside["state"], outside["consecutive_good"]) == ("live", 2)

    lone = cs.update_entry(quarantined, good_row(), now=at(900))
    assert (lone["state"], lone["consecutive_good"]) == ("degraded", 1)


def test_deprecation_signal_holds_while_present_and_yields_to_quarantine() -> None:
    flagged = fold([(at(0), good_row(deprecation_signal="expired"))])
    assert (flagged["state"], flagged["score"]) == ("deprecation-candidate", 100)
    cleared = cs.update_entry(flagged, good_row(), now=at(60))
    assert cleared["state"] == "live"

    both = fold(
        [
            (at(0), bad_row()),
            (at(100), bad_row()),
            (at(200), bad_row(deprecation_signal="status_not_live")),
        ]
    )
    assert both["state"] == "quarantined"


def test_retired_is_preserved_and_never_set_by_the_script() -> None:
    human = entry_for("retired", retired_by="owner 2026-09-01")
    after = cs.update_entry(human, good_row(), now=at(0))
    assert after["state"] == "retired"
    assert after["retired_by"] == "owner 2026-09-01"
    assert after["score"] == 100

    fresh = fold([(at(0), bad_row())] * 5)
    assert "retired_by" not in fresh
    assert fresh["state"] != "retired"


def test_update_entry_honours_producer_history() -> None:
    entry = cs.update_entry(
        None,
        bad_row(last_success_at=at(hours=-2), latency_ms=100, baseline_latency_ms=50),
        now=at(0),
    )
    assert entry["components"]["freshness"] == 10
    assert entry["components"]["latency"] == 10
    assert entry["last_probe"]["baseline_latency_ms"] == 50
    assert entry["last_probe"]["last_success_at"] == at(hours=-2)

    no_latency = cs.update_entry(entry, good_row(latency_ms=None), now=at(60))
    assert no_latency["last_probe"]["baseline_latency_ms"] == 50
    assert no_latency["components"]["latency"] == 0


def test_update_scores_folds_rows_and_keeps_other_entries_sorted() -> None:
    state = {
        "schemaVersion": 1,
        "updated_at": at(-60),
        "endpoints": {"zeta": entry_for("live"), EP: entry_for("degraded")},
    }
    new = cs.update_scores(state, [good_row(), {"id": "alpha", "ok": False}], now=NOW)
    assert list(new["endpoints"]) == ["alpha", EP, "zeta"]
    assert new["endpoints"]["zeta"] == entry_for("live")
    assert new["endpoints"][EP]["state"] == "degraded"
    assert new["endpoints"]["alpha"]["state"] == "degraded"
    assert new["updated_at"] == NOW
    assert cs.validate_state(new) is new
    with pytest.raises(cs.CapabilityScoreError):
        cs.update_scores(state, [{"id": EP}], now=NOW)


def test_summarise_counts_every_state() -> None:
    state = {
        "schemaVersion": 1,
        "updated_at": NOW,
        "endpoints": {
            "a": entry_for("live"),
            "b": entry_for("degraded"),
            "c": entry_for("quarantined"),
            "d": entry_for("deprecation-candidate"),
            "e": entry_for("retired", retired_by="x"),
        },
    }
    assert cs.summarise(state, updated=2) == {
        "endpoints": 5,
        "updated": 2,
        "live": 1,
        "degraded": 1,
        "quarantined": 1,
        "deprecation_candidate": 1,
        "retired": 1,
    }


# ---------------------------------------------------------------------------
# Rows from the mcp-liveness ladder report
# ---------------------------------------------------------------------------
def ladder_report() -> dict[str, Any]:
    return {
        "mode": "all",
        "duration_ms": 12,
        "rungs": {
            "L0": {"status": "ok", "items": []},
            "L1": {
                "status": "down",
                "items": [
                    {
                        "name": "basic-memory",
                        "state": "up",
                        "tools_ok": True,
                        "latency_ms": 12,
                    },
                    {"name": "agent-mail", "state": "down", "latency_ms": None},
                    7,
                ],
            },
            "L2": {
                "status": "changed",
                "items": [
                    {"server": "basic-memory", "status": "changed", "reviewed": True},
                    {"server": "agent-mail", "status": "weird"},
                    {"status": "no server key"},
                ],
            },
            "L3": {
                "status": "ok",
                "items": [
                    {
                        "endpoint": "ollama",
                        "status": "up",
                        "url": "http://127.0.0.1:11434/v1",
                        "latency_ms": 40,
                        "claims": ["wire.completions", "features.usage"],
                        "registry_models": ["qwen2.5:7b"],
                    },
                    {
                        "endpoint": "lmstudio",
                        "status": "down",
                        "url": "http://127.0.0.1:1234/v1",
                        "latency_ms": None,
                        "claims": ["features.tools"],
                        "registry_models": "not-a-list",
                    },
                    {
                        "endpoint": "cursor-auth2api",
                        "status": "up",
                        "url": 42,
                        "latency_ms": 5,
                        "claims": [],
                    },
                    {"endpoint": "openrouter", "status": "skipped", "reason": "hosted"},
                ],
            },
            "L4": {
                "status": "ok",
                "items": [
                    {
                        "endpoint": "ollama",
                        "status": "ok",
                        "observed": {"wire.completions": True, "features.usage": False},
                    },
                    {"endpoint": "lmstudio", "status": "error"},
                    {"endpoint": "cursor-auth2api", "status": "ok", "observed": "x"},
                    {"endpoint": "openrouter", "status": "skipped"},
                ],
            },
            "L5": {
                "status": "findings",
                "items": [{"tool": "mcp-scan", "flagged": ["basic-memory"]}],
            },
        },
    }


def test_rows_from_ladder_maps_every_rung() -> None:
    diff = {
        "expired": [{"feed": "ollama", "id": "qwen2.5:7b"}],
        "status_not_live": [],
        "decommissioned_hosts": ["127.0.0.1"],
    }
    rows = {row["id"]: row for row in cs.rows_from_ladder(ladder_report(), diff)}
    assert set(rows) == {
        "basic-memory",
        "agent-mail",
        "ollama",
        "lmstudio",
        "cursor-auth2api",
    }

    memory = rows["basic-memory"]
    assert memory["ok"] is True
    assert memory["observed"] == {"tools": True}
    assert (memory["digest"], memory["reviewed"], memory["scan"]) == (
        "changed",
        True,
        "findings",
    )
    assert memory["claim_agreement"] is None
    mail = rows["agent-mail"]
    assert mail["ok"] is False
    assert mail["observed"] == {}
    assert (mail["digest"], mail["reviewed"], mail["scan"]) == ("none", False, "clean")

    ollama = rows["ollama"]
    assert ollama["observed"] == {"wire.completions": True, "features.usage": False}
    assert ollama["claim_agreement"] is False
    assert ollama["deprecation_signal"] == "expired"
    lmstudio = rows["lmstudio"]
    assert lmstudio["ok"] is False
    assert lmstudio["observed"] == {}
    assert lmstudio["claim_agreement"] is None
    assert lmstudio["deprecation_signal"] == "decommissioned_host"
    bridge = rows["cursor-auth2api"]
    assert bridge["observed"] == {}
    assert bridge["deprecation_signal"] is None

    for row in rows.values():
        cs.validate_row(row)


def test_rows_from_ladder_without_a_diff_or_l5_run() -> None:
    report = ladder_report()
    report["rungs"]["L5"] = {"status": "skipped", "items": []}
    rows = {row["id"]: row for row in cs.rows_from_ladder(report)}
    assert rows["basic-memory"]["scan"] == "skipped"
    assert rows["ollama"]["deprecation_signal"] is None

    report["rungs"]["L5"] = {"status": "clean", "items": [{"flagged": ["other"]}]}
    assert cs.scan_verdict("basic-memory", report) == "clean"


def test_rows_from_ladder_tolerates_malformed_rungs() -> None:
    assert cs.rows_from_ladder({"rungs": "nope"}) == []
    assert cs.rows_from_ladder({"rungs": {"L1": "x", "L3": {"items": None}}}) == []
    assert cs._items({"rungs": {"L1": {"items": [1, "two"]}}}, "L1") == []
    assert cs._strings(("a", 1)) == []


@pytest.mark.parametrize(
    ("url", "remote_ids", "diff", "signal"),
    [
        ("http://h/v1", ["m"], None, None),
        ("http://h/v1", ["m"], {"expired": "nope"}, None),
        ("http://h/v1", ["m"], {"expired": [1, {"feed": "other", "id": "m"}]}, None),
        ("http://h/v1", ["m"], {"expired": [{"feed": EP, "id": "other"}]}, None),
        (
            "http://h/v1",
            ["m"],
            {"status_not_live": [{"feed": EP, "id": "m"}]},
            "status_not_live",
        ),
        ("http://h/v1", [], {"decommissioned_hosts": ["h"]}, "decommissioned_host"),
        ("http://h/v1", [], {"decommissioned_hosts": "h"}, None),
        (None, [], {"decommissioned_hosts": [None]}, None),
    ],
)
def test_deprecation_signal(
    url: Any, remote_ids: list[str], diff: dict[str, Any] | None, signal: str | None
) -> None:
    assert cs.deprecation_signal(EP, url, remote_ids, diff) == signal


def test_rows_from_input_accepts_rows_or_a_ladder_and_nothing_else() -> None:
    assert cs.rows_from_input({"rows": [bad_row()]}, None) == [bad_row()]
    assert cs.rows_from_input(ladder_report(), None)
    with pytest.raises(cs.CapabilityScoreError, match="must be a JSON object"):
        cs.rows_from_input([], None)
    with pytest.raises(cs.CapabilityScoreError, match="neither"):
        cs.rows_from_input({"rows": "x"}, None)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def test_load_json_file_errors(tmp_path: Path) -> None:
    with pytest.raises(cs.CapabilityScoreError, match="not readable"):
        cs.load_json_file(tmp_path / "missing.json", "input")
    bad = tmp_path / "bad.json"
    bad.write_text("nope", encoding="utf-8")
    with pytest.raises(cs.CapabilityScoreError, match="not valid JSON"):
        cs.load_json_file(bad, "input")


def test_supervision_policy(tmp_path: Path) -> None:
    assert cs.supervision_policy(tmp_path / "absent.json") == (3, 600)
    config = tmp_path / "agents.json"
    config.write_text("[]", encoding="utf-8")
    assert cs.supervision_policy(config) == (3, 600)
    config.write_text(json.dumps({"mcp": "x"}), encoding="utf-8")
    assert cs.supervision_policy(config) == (3, 600)
    config.write_text(json.dumps({"mcp": {"supervision": {}}}), encoding="utf-8")
    assert cs.supervision_policy(config) == (3, 600)
    config.write_text(
        json.dumps(
            {
                "mcp": {
                    "supervision": {"failureThreshold": 2, "failureWindowSeconds": 60}
                }
            }
        ),
        encoding="utf-8",
    )
    assert cs.supervision_policy(config) == (2, 60)
    assert cs.supervision_policy(cs.DEFAULT_AGENTS_CONFIG) == (3, 600)


def cli(
    tmp_path: Path, *extra: str, payload: Any = None, agents: Any = None
) -> tuple[int, str]:
    state = tmp_path / "state" / "capability-scores.json"
    source = tmp_path / "input.json"
    if payload is None:
        payload = {"rows": [good_row(), {"id": "agent-mail", "ok": False}]}
    source.write_text(json.dumps(payload), encoding="utf-8")
    config = tmp_path / "agents.json"
    config.write_text(json.dumps(agents or {}), encoding="utf-8")
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = cs.main(
            [
                "--state",
                str(state),
                "--input",
                str(source),
                "--agents-config",
                str(config),
                *extra,
            ]
        )
    return code, buffer.getvalue()


def test_cli_writes_the_sidecar_and_prints_the_success_line(tmp_path: Path) -> None:
    code, out = cli(tmp_path)
    assert code == 0
    lines = out.splitlines()
    assert lines[-1] == (
        "SUCCESS:capability-score endpoints=2 live=1 degraded=1 quarantined=0 "
        "deprecation_candidate=0 retired=0 updated=2"
    )
    assert f"  {EP}: live (100)" in lines
    assert "  agent-mail: degraded (25)" in lines
    state = json.loads((tmp_path / "state" / "capability-scores.json").read_text())
    assert cs.validate_state(state)["endpoints"][EP]["state"] == "live"

    code, out = cli(tmp_path)
    assert code == 0
    assert (
        json.loads((tmp_path / "state" / "capability-scores.json").read_text())[
            "endpoints"
        ][EP]["consecutive_good"]
        == 2
    )


def test_cli_json_output_and_policy_from_agents_config(tmp_path: Path) -> None:
    agents = {
        "mcp": {"supervision": {"failureThreshold": 1, "failureWindowSeconds": 30}}
    }
    code, out = cli(tmp_path, "--json", agents=agents)
    assert code == 0
    body, marker = out.rsplit("\n", 2)[0], out.splitlines()[-1]
    summary = json.loads(body)
    assert summary["policy"] == {"failureThreshold": 1, "failureWindowSeconds": 30}
    assert summary["endpoints"]["agent-mail"]["state"] == "quarantined"
    assert summary["counts"]["quarantined"] == 1
    assert marker.startswith("SUCCESS:capability-score endpoints=2 live=1 degraded=0 ")


def test_cli_consumes_a_ladder_report_with_a_catalog_diff(tmp_path: Path) -> None:
    diff = tmp_path / "last-diff.json"
    diff.write_text(
        json.dumps({"expired": [{"feed": "ollama", "id": "qwen2.5:7b"}]}),
        encoding="utf-8",
    )
    code, out = cli(tmp_path, "--catalog-diff", str(diff), payload=ladder_report())
    assert code == 0
    assert "  ollama: deprecation-candidate" in out
    assert "deprecation_candidate=1" in out.splitlines()[-1]

    diff.write_text("[]", encoding="utf-8")
    code, out = cli(tmp_path, "--catalog-diff", str(diff), payload=ladder_report())
    assert code == 2
    assert out.strip() == "FAILED:capability-score catalog diff must be a JSON object"


def test_cli_failures_are_one_terminal_line(tmp_path: Path, monkeypatch: Any) -> None:
    code, out = cli(tmp_path, payload={"rows": [{"id": EP, "ok": True, "x": 1}]})
    assert code == 2
    assert out.strip() == "FAILED:capability-score row has unknown key(s): x"

    def boom(path: Path, payload: Any) -> None:
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(cs, "atomic_write_json", boom)
    code, out = cli(tmp_path)
    assert code == 2
    assert out.strip() == "FAILED:capability-score RuntimeError: disk on fire"


def test_cli_reads_sys_argv_when_argv_is_none(tmp_path: Path, monkeypatch: Any) -> None:
    source = tmp_path / "input.json"
    source.write_text(json.dumps({"rows": [bad_row()]}), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "capability_score.py",
            "--state",
            str(tmp_path / "scores.json"),
            "--input",
            str(source),
            "--agents-config",
            str(tmp_path / "absent.json"),
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        assert cs.main() == 0
    assert (
        buffer.getvalue()
        .splitlines()[-1]
        .startswith("SUCCESS:capability-score endpoints=1")
    )


def test_run_refuses_to_overwrite_a_malformed_sidecar(tmp_path: Path) -> None:
    state = tmp_path / "scores.json"
    state.write_text(
        json.dumps({"schemaVersion": 1, "updated_at": NOW, "endpoints": {}, "x": 1})
    )
    source = tmp_path / "input.json"
    source.write_text(json.dumps({"rows": [bad_row()]}), encoding="utf-8")
    with pytest.raises(cs.CapabilityScoreError, match="unknown key"):
        cs.run(
            state,
            source,
            agents_config=tmp_path / "none.json",
            catalog_diff=None,
            now=NOW,
        )
    assert json.loads(state.read_text())["x"] == 1
