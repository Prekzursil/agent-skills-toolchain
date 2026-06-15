"""Tests for core/loadout.py — read/write/add/remove/apply loadout defaults."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import loadout as lm  # noqa: E402
from core.models import Loadout  # noqa: E402

# ── helpers ────────────────────────────────────────────────────────────────────

DISABLED_DEFAULTS = {
    "_comment": "Option G: Two-Tier MCP",
    "_tier1_enabled": ["plugin:local-mcp-bridge:tavily"],
    "disabledMcpServers": [
        "claude.ai PubMed",
        "plugin:semgrep:semgrep",
        "plugin:playwright:playwright",
    ],
}


def _make_defaults(tmp_path: Path) -> Path:
    p = tmp_path / ".mcp-disabled-defaults.json"
    p.write_text(json.dumps(DISABLED_DEFAULTS), encoding="utf-8")
    return p


# ── read_loadout ───────────────────────────────────────────────────────────────


class TestReadLoadout:
    def test_reads_disabled_ids(self, tmp_path: Path):
        p = _make_defaults(tmp_path)
        lo = lm.read_loadout(p)
        assert "claude.ai PubMed" in lo.disabled_ids
        assert "plugin:semgrep:semgrep" in lo.disabled_ids

    def test_name_is_defaults(self, tmp_path: Path):
        p = _make_defaults(tmp_path)
        lo = lm.read_loadout(p)
        assert lo.name == "defaults"

    def test_raw_preserves_extra_keys(self, tmp_path: Path):
        p = _make_defaults(tmp_path)
        lo = lm.read_loadout(p)
        assert "_comment" in lo.raw
        assert "_tier1_enabled" in lo.raw

    def test_missing_file_returns_empty_loadout(self, tmp_path: Path):
        lo = lm.read_loadout(tmp_path / "nope.json")
        assert lo.disabled_ids == []

    def test_malformed_json_returns_empty(self, tmp_path: Path):
        p = tmp_path / ".mcp-disabled-defaults.json"
        p.write_text("{ not valid json", encoding="utf-8")
        lo = lm.read_loadout(p)
        assert lo.disabled_ids == []


# ── write_loadout ──────────────────────────────────────────────────────────────


class TestWriteLoadout:
    def test_writes_disabled_ids(self, tmp_path: Path):
        p = tmp_path / "defaults.json"
        lo = Loadout(disabled_ids=["svc-a", "svc-b"])
        lm.write_loadout(lo, p, backup=False)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["disabledMcpServers"] == ["svc-a", "svc-b"]

    def test_preserves_unknown_keys(self, tmp_path: Path):
        p = _make_defaults(tmp_path)
        lo = lm.read_loadout(p)
        lo.disabled_ids.append("new-svc")
        lm.write_loadout(lo, p, backup=False)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "_comment" in data
        assert "_tier1_enabled" in data
        assert "new-svc" in data["disabledMcpServers"]

    def test_backup_created(self, tmp_path: Path):
        p = _make_defaults(tmp_path)
        lo = lm.read_loadout(p)
        lm.write_loadout(lo, p, backup=True)
        bak_dir = p.parent / ".mcp-manager-backups"
        baks = list(bak_dir.glob("*.bak"))
        assert len(baks) >= 1

    def test_creates_parent_directory(self, tmp_path: Path):
        p = tmp_path / "nested" / "dir" / "defaults.json"
        lo = Loadout(disabled_ids=["x"])
        lm.write_loadout(lo, p, backup=False)
        assert p.exists()


# ── add / remove ───────────────────────────────────────────────────────────────


class TestAddRemove:
    def test_add_returns_true_on_change(self, tmp_path: Path):
        p = _make_defaults(tmp_path)
        changed = lm.add_to_loadout("new-server", p, backup=False)
        assert changed is True

    def test_add_idempotent(self, tmp_path: Path):
        p = _make_defaults(tmp_path)
        assert lm.add_to_loadout("claude.ai PubMed", p, backup=False) is False

    def test_add_persists(self, tmp_path: Path):
        p = _make_defaults(tmp_path)
        lm.add_to_loadout("brand-new", p, backup=False)
        lo = lm.read_loadout(p)
        assert "brand-new" in lo.disabled_ids

    def test_remove_returns_true_on_change(self, tmp_path: Path):
        p = _make_defaults(tmp_path)
        assert lm.remove_from_loadout("claude.ai PubMed", p, backup=False) is True

    def test_remove_idempotent(self, tmp_path: Path):
        p = _make_defaults(tmp_path)
        assert lm.remove_from_loadout("not-there", p, backup=False) is False

    def test_remove_persists(self, tmp_path: Path):
        p = _make_defaults(tmp_path)
        lm.remove_from_loadout("claude.ai PubMed", p, backup=False)
        lo = lm.read_loadout(p)
        assert "claude.ai PubMed" not in lo.disabled_ids


# ── apply_loadout_to_project ───────────────────────────────────────────────────


class TestApplyLoadoutToProject:
    def test_applies_disabled_ids_to_claude_json(self, tmp_path: Path):
        from core import claude_adapter

        proj = "C:/my/project"
        cj = tmp_path / ".claude.json"
        cj.write_text(json.dumps({"projects": {proj: {"disabledMcpServers": []}}}),
                      encoding="utf-8")
        lo = Loadout(disabled_ids=["plugin:a:x", "plugin:b:y"])
        changed = lm.apply_loadout_to_project(lo, cj, proj)
        assert set(changed) == {"plugin:a:x", "plugin:b:y"}
        data = json.loads(cj.read_text(encoding="utf-8"))
        arr = data["projects"][proj]["disabledMcpServers"]
        assert "plugin:a:x" in arr
        assert "plugin:b:y" in arr

    def test_already_disabled_not_in_changed(self, tmp_path: Path):
        proj = "C:/p"
        cj = tmp_path / ".claude.json"
        cj.write_text(json.dumps({"projects": {proj: {"disabledMcpServers": ["plugin:a:x"]}}}),
                      encoding="utf-8")
        lo = Loadout(disabled_ids=["plugin:a:x", "plugin:b:y"])
        changed = lm.apply_loadout_to_project(lo, cj, proj)
        assert "plugin:a:x" not in changed
        assert "plugin:b:y" in changed
