"""Tests for the claude.ai remote-connector census (surface-census undercount fix).

The CLI-side inventory (``core/inventory.py``) is structurally blind to claude.ai
remote connectors: they surface only as runtime ``mcp__claude_ai_*`` namespaces and
are never persisted to disk, so a pure-code census reports the CLI count (measured
68) as if it were the whole surface (measured true live ~88 = 68 + 20). These tests
pin the merged total, the CLI-vs-claude.ai separation, the LIVE/EVER reconciliation,
and the never-a-silent-zero fallback.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import surface_census as sc  # noqa: E402

# The 20 LIVE claude.ai connector namespaces (this session's manifest ground truth).
LIVE_20 = [
    "AdisInsight",
    "BioRender",
    "Biomni_Lab",
    "Boltz_API",
    "ChEMBL_2",
    "Consensus",
    "Descript",
    "EDEN_by_Basecamp_Research",
    "Elicit",
    "Felt_Maps",
    "Inductive_Bio",
    "Mozilla_MDN",
    "Open_Targets",
    "Owkin",
    "Parallel_Search",
    "Scholar_Gateway",
    "Synapse_org",
    "Synthesize_Bio",
    "TomTom_Maps",
    "Wolfram",
]
# LIVE but absent on disk (the array lags newly-connected connectors).
STALE_3 = ["AdisInsight", "Felt_Maps", "TomTom_Maps"]


def _write_manifest(path: Path, connectors: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"captured": "2026-07-24", "connectors": connectors}),
        encoding="utf-8",
    )
    return path


def _write_claude_json(
    path: Path,
    *,
    mcp_servers: dict[str, object] | None = None,
    ever: list[str] | None = None,
    gate: bool | None = None,
) -> Path:
    data: dict[str, object] = {"mcpServers": mcp_servers or {}}
    if ever is not None:
        data["claudeAiMcpEverConnected"] = ever
    if gate is not None:
        # nested exactly like the drifting statsig cache the gate lives in
        data["statsigCache"] = {"values": {"gates": {sc.GATE_KEY: gate}}}
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _documented_home(tmp_path: Path) -> tuple[Path, Path]:
    """A home reproducing the measured scenario: 68 CLI + 20 live + 43 ever -> 88."""
    shared_17 = [n for n in LIVE_20 if n not in STALE_3]  # live INTER ever
    superset_26 = [f"Superset{i:02d}" for i in range(1, 27)]  # ever ONLY (disconnected)
    ever_43 = [f"claude.ai {n}" for n in shared_17 + superset_26]
    _write_claude_json(
        tmp_path / ".claude.json",
        mcp_servers={f"cli-server-{i:02d}": {} for i in range(68)},
        ever=ever_43,
        gate=True,
    )
    manifest = _write_manifest(tmp_path / "live.json", LIVE_20)
    return tmp_path, manifest


# --- name normalization -----------------------------------------------------


@pytest.mark.parametrize(
    ("display", "expected"),
    [
        ("claude.ai ChEMBL (2)", "ChEMBL_2"),
        ("claude.ai Synapse.org", "Synapse_org"),
        ("claude.ai EDEN by Basecamp Research", "EDEN_by_Basecamp_Research"),
        ("claude.ai Wolfram", "Wolfram"),
        ("Wolfram", "Wolfram"),  # no prefix -> unchanged
    ],
)
def test_normalize_display_name(display: str, expected: str) -> None:
    assert sc.normalize_display_name(display) == expected


# --- feature-gate discovery -------------------------------------------------


def test_find_gate_present_true() -> None:
    assert sc._find_gate({sc.GATE_KEY: True}) is True


def test_find_gate_present_false() -> None:
    assert sc._find_gate({sc.GATE_KEY: False}) is False


def test_find_gate_nested_in_list_and_dict() -> None:
    obj = {"a": [{"b": {sc.GATE_KEY: True}}]}
    assert sc._find_gate(obj) is True


def test_find_gate_absent_with_scalar_and_list_branches() -> None:
    # a scalar value (skipped) AND a list value (traversed) but no gate anywhere
    obj = {"scalar": "x", "nums": [1, 2], "nested": {"other": "y"}}
    assert sc._find_gate(obj) is False


# --- source loaders ---------------------------------------------------------


def test_load_json_missing_file_is_empty(tmp_path: Path) -> None:
    assert sc._load_json(tmp_path / "nope.json") == {}


def test_manifest_connectors_none_manifest() -> None:
    assert sc._manifest_connectors(None) == set()


def test_manifest_connectors_filters_non_strings(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path / "m.json", ["A", "B"])
    # inject a non-string entry that must be ignored
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    raw["connectors"] = ["A", 5, "B"]
    manifest.write_text(json.dumps(raw), encoding="utf-8")
    assert sc._manifest_connectors(manifest) == {"A", "B"}


def test_manifest_connectors_missing_key(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"captured": "x"}), encoding="utf-8")
    assert sc._manifest_connectors(path) == set()


def test_ever_from_data_filters_non_strings() -> None:
    data = {"claudeAiMcpEverConnected": ["claude.ai Wolfram", 7, "claude.ai Elicit"]}
    assert sc._ever_from_data(data) == {"Wolfram", "Elicit"}


def test_ever_from_data_missing_key() -> None:
    assert sc._ever_from_data({}) == set()


# --- connector reconciliation ----------------------------------------------


def test_claude_ai_connectors_with_manifest(tmp_path: Path) -> None:
    _, manifest = _documented_home(tmp_path)
    conn = sc.claude_ai_connectors(tmp_path / ".claude.json", manifest)
    assert conn["gate_enabled"] is True
    assert conn["count_live"] == 20
    assert conn["count_ever"] == 43
    assert conn["live_missing_on_disk"] == sorted(STALE_3)
    assert len(conn["ever_not_live"]) == 26
    assert conn["reported_count"] == 20
    assert conn["reported_basis"] == "manifest"


def test_claude_ai_connectors_fallback_when_no_manifest(tmp_path: Path) -> None:
    _documented_home(tmp_path)
    # a manifest path that does not exist -> LIVE empty -> EVER fallback, never 0
    conn = sc.claude_ai_connectors(tmp_path / ".claude.json", tmp_path / "absent.json")
    assert conn["count_live"] == 0
    assert conn["reported_count"] == 43
    assert conn["reported_basis"] == "ever-fallback(overcount)"


# --- merged surface census --------------------------------------------------


def test_surface_census_documented_88(tmp_path: Path) -> None:
    home, manifest = _documented_home(tmp_path)
    rep = sc.surface_census(home, project_path=None, live_manifest=manifest)
    assert rep["schema"] == "mcp-surface-census/v1"
    # the separation: CLI-side and claude.ai-side are distinct, never conflated
    assert rep["cli_side_count"] == 68
    assert rep["claude_ai_live_count"] == 20
    assert rep["claude_ai_ever_count"] == 43
    # the merged total: 68 + 20 = 88 (the fix)
    assert rep["true_live_total"] == 88
    assert rep["claude_ai_reported_basis"] == "manifest"
    assert rep["claude_ai_gate_enabled"] is True
    assert rep["live_missing_on_disk"] == sorted(STALE_3)
    assert rep["ever_not_live_count"] == 26


def test_surface_census_merge_is_cli_plus_live(tmp_path: Path) -> None:
    # omit `ever` (default None) so the census sees no EVER key at all
    _write_claude_json(
        tmp_path / ".claude.json",
        mcp_servers={"a": {}, "b": {}, "c": {}},
    )
    manifest = _write_manifest(tmp_path / "m.json", ["X", "Y"])
    rep = sc.surface_census(tmp_path, project_path=None, live_manifest=manifest)
    assert rep["cli_side_count"] == 3
    assert rep["claude_ai_live_count"] == 2
    assert rep["true_live_total"] == 5  # 3 + 2, generic merge


def test_surface_census_default_manifest_path(tmp_path: Path) -> None:
    _write_claude_json(tmp_path / ".claude.json", mcp_servers={"a": {}}, ever=[])
    # write the manifest at the STABLE default location the refresh loop targets
    _write_manifest(sc.default_manifest_path(tmp_path), ["Only"])
    rep = sc.surface_census(tmp_path, project_path=None, live_manifest=None)
    assert rep["claude_ai_live_count"] == 1
    assert rep["claude_ai_reported_basis"] == "manifest"
    assert rep["true_live_total"] == 2


def test_surface_census_fallback_never_zero(tmp_path: Path) -> None:
    _write_claude_json(
        tmp_path / ".claude.json",
        mcp_servers={"a": {}, "b": {}},
        ever=["claude.ai Wolfram", "claude.ai Elicit"],
    )
    # no manifest anywhere -> reported falls back to EVER (2), total = 2 + 2, not 2 + 0
    rep = sc.surface_census(tmp_path, project_path=None, live_manifest=None)
    assert rep["claude_ai_reported_count"] == 2
    assert rep["claude_ai_reported_basis"] == "ever-fallback(overcount)"
    assert rep["true_live_total"] == 4


# --- CLI --------------------------------------------------------------------


def test_main_with_project_and_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    home, manifest = _documented_home(tmp_path)
    code = sc.main(
        ["--home", str(home), "--project", "none", "--manifest", str(manifest)]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["schema"] == "mcp-surface-census/v1"
    assert out["true_live_total"] == 88


def test_main_defaults_project_from_home(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_claude_json(tmp_path / ".claude.json", mcp_servers={"a": {}}, ever=[])
    manifest = _write_manifest(tmp_path / "m.json", ["Only"])
    code = sc.main(["--home", str(tmp_path), "--manifest", str(manifest)])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["true_live_total"] == 2
