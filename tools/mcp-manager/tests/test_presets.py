"""Tests for core/presets.py — named preset catalog, resolver, and apply."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import presets as pm  # noqa: E402


# ── normalize_id ──────────────────────────────────────────────────────────────


class TestNormalizeId:
    def test_plain_name(self):
        assert pm.normalize_id("tavily") == "tavily"

    def test_strips_claude_ai_prefix(self):
        assert pm.normalize_id("claude.ai PubMed") == "pubmed"

    def test_strips_plugin_namespace(self):
        assert pm.normalize_id("plugin:semgrep:semgrep") == "semgrep"

    def test_drops_trailing_mcp_token(self):
        assert pm.normalize_id("ida-pro-mcp") == "idapro"
        assert pm.normalize_id("ida-pro") == "idapro"

    def test_drops_leading_mcp_token(self):
        assert pm.normalize_id("mcp-graphql") == "graphql"

    def test_hyphens_and_underscores_collapse(self):
        assert pm.normalize_id("github_cli") == pm.normalize_id("github-cli")

    def test_figma_distinct_from_figma_rest(self):
        assert pm.normalize_id("figma") != pm.normalize_id("figma-rest")

    def test_bare_mcp_not_stripped_when_only_token(self):
        # a single 'mcp' token is preserved (guard: len>1 required)
        assert pm.normalize_id("mcp") == "mcp"


# ── fuzzy_filter ──────────────────────────────────────────────────────────────


class TestFuzzyFilter:
    ITEMS = ["ida-pro-mcp", "ghidra-mcp", "basic-memory", "tavily"]

    def test_empty_query_returns_all(self):
        assert pm.fuzzy_filter("", self.ITEMS) == self.ITEMS

    def test_substring_match(self):
        assert pm.fuzzy_filter("ghid", self.ITEMS) == ["ghidra-mcp"]

    def test_subsequence_match(self):
        # 'idap' is a subsequence of 'idapromcp'
        assert "ida-pro-mcp" in pm.fuzzy_filter("idap", self.ITEMS)

    def test_no_match_returns_empty(self):
        assert pm.fuzzy_filter("zzzz", self.ITEMS) == []

    def test_whitespace_query_returns_all(self):
        assert pm.fuzzy_filter("   ", self.ITEMS) == self.ITEMS


# ── default_catalog / read_catalog ────────────────────────────────────────────


class TestReadCatalog:
    def test_default_catalog_has_core_and_presets(self):
        cat = pm.default_catalog()
        assert "basic-memory" in cat.core
        assert "re" in cat.presets
        assert "ida-pro-mcp" in cat.presets["re"]

    def test_missing_file_returns_seed(self, tmp_path: Path):
        cat = pm.read_catalog(tmp_path / "nope.json")
        assert cat.core == pm.SEED_CORE

    def test_malformed_returns_seed(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        p.write_text("{ not json", encoding="utf-8")
        cat = pm.read_catalog(p)
        assert cat.core == pm.SEED_CORE

    def test_reads_valid_file(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        p.write_text(
            json.dumps({"core": ["a"], "presets": {"x": ["b", "c"]}}),
            encoding="utf-8",
        )
        cat = pm.read_catalog(p)
        assert cat.core == ["a"]
        assert cat.presets == {"x": ["b", "c"]}

    def test_non_list_core_becomes_empty(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        p.write_text(json.dumps({"core": "notalist"}), encoding="utf-8")
        cat = pm.read_catalog(p)
        assert cat.core == []

    def test_non_dict_presets_becomes_empty(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        p.write_text(json.dumps({"presets": ["x"]}), encoding="utf-8")
        cat = pm.read_catalog(p)
        assert cat.presets == {}

    def test_non_list_preset_member_skipped(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        p.write_text(
            json.dumps({"presets": {"good": ["a"], "bad": "x"}}), encoding="utf-8"
        )
        cat = pm.read_catalog(p)
        assert cat.presets == {"good": ["a"]}


# ── write_catalog / ensure_catalog_file ───────────────────────────────────────


class TestWriteCatalog:
    def test_writes_core_and_presets(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        cat = pm.PresetCatalog(core=["a"], presets={"x": ["b"]})
        pm.write_catalog(cat, p, backup=False)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["core"] == ["a"]
        assert data["presets"] == {"x": ["b"]}

    def test_preserves_unknown_keys(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        p.write_text(json.dumps({"_comment": "keep me", "core": []}), encoding="utf-8")
        cat = pm.read_catalog(p)
        cat.core.append("new")
        pm.write_catalog(cat, p, backup=False)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["_comment"] == "keep me"
        assert "new" in data["core"]

    def test_seeds_comment_from_catalog_raw(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        pm.write_catalog(pm.default_catalog(), p, backup=False)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "_comment" in data

    def test_backup_created_when_file_exists(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        pm.write_catalog(pm.PresetCatalog(core=["a"]), p, backup=False)
        pm.write_catalog(pm.PresetCatalog(core=["b"]), p, backup=True)
        baks = list((p.parent / ".mcp-manager-backups").glob("*.bak"))
        assert len(baks) >= 1

    def test_creates_parent_directory(self, tmp_path: Path):
        p = tmp_path / "nested" / "presets.json"
        pm.write_catalog(pm.PresetCatalog(core=["a"]), p, backup=False)
        assert p.exists()

    def test_ensure_creates_when_absent(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        cat = pm.ensure_catalog_file(p)
        assert p.exists()
        assert cat.core == pm.SEED_CORE

    def test_ensure_returns_existing(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        p.write_text(json.dumps({"core": ["only"]}), encoding="utf-8")
        cat = pm.ensure_catalog_file(p)
        assert cat.core == ["only"]


# ── save_preset / delete_preset ───────────────────────────────────────────────


class TestSaveDelete:
    def test_save_new_returns_true(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        assert pm.save_preset("foo", ["a", "b"], p, backup=False) is True
        assert pm.read_catalog(p).presets["foo"] == ["a", "b"]

    def test_save_unchanged_returns_false(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        pm.save_preset("foo", ["a"], p, backup=False)
        assert pm.save_preset("foo", ["a"], p, backup=False) is False

    def test_save_overwrite(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        pm.save_preset("foo", ["a"], p, backup=False)
        assert pm.save_preset("foo", ["a", "b"], p, backup=False) is True
        assert pm.read_catalog(p).presets["foo"] == ["a", "b"]

    def test_delete_existing(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        pm.save_preset("foo", ["a"], p, backup=False)
        assert pm.delete_preset("foo", p, backup=False) is True
        assert "foo" not in pm.read_catalog(p).presets

    def test_delete_missing(self, tmp_path: Path):
        p = tmp_path / "presets.json"
        pm.ensure_catalog_file(p)
        assert pm.delete_preset("nope", p, backup=False) is False


# ── PresetCatalog helpers ─────────────────────────────────────────────────────


class TestCatalogHelpers:
    def test_names_sorted(self):
        cat = pm.PresetCatalog(presets={"z": [], "a": []})
        assert cat.names() == ["a", "z"]

    def test_members_of_named(self):
        cat = pm.PresetCatalog(presets={"x": ["a", "b"]})
        assert cat.members("x") == ["a", "b"]

    def test_members_of_core(self):
        cat = pm.PresetCatalog(core=["c"], presets={})
        assert cat.members("core") == ["c"]

    def test_members_unknown_is_none(self):
        cat = pm.PresetCatalog(presets={})
        assert cat.members("nope") is None


# ── resolve_disabled ──────────────────────────────────────────────────────────


class TestResolveDisabled:
    def _cat(self) -> pm.PresetCatalog:
        return pm.PresetCatalog(
            core=["basic-memory", "tavily"],
            presets={"re": ["ida-pro-mcp", "ghidra-mcp"], "empty": ["nomatch"]},
        )

    def test_core_only_disables_everything_else(self):
        inv = ["basic-memory", "tavily", "ida-pro-mcp", "docker"]
        res = pm.resolve_disabled(self._cat(), [], inv)
        assert set(res.to_enable) == {"basic-memory", "tavily"}
        assert set(res.to_disable) == {"ida-pro-mcp", "docker"}

    def test_compose_presets_union(self):
        inv = ["basic-memory", "ida-pro-mcp", "ghidra-mcp", "docker"]
        res = pm.resolve_disabled(self._cat(), ["re"], inv)
        assert set(res.to_enable) == {"basic-memory", "ida-pro-mcp", "ghidra-mcp"}
        assert res.to_disable == ["docker"]

    def test_core_keyword_is_noop_beyond_core(self):
        inv = ["basic-memory", "docker"]
        res = pm.resolve_disabled(self._cat(), ["core"], inv)
        assert res.to_enable == ["basic-memory"]
        assert res.to_disable == ["docker"]

    def test_unknown_preset_reported(self):
        res = pm.resolve_disabled(self._cat(), ["bogus"], ["basic-memory"])
        assert res.unknown_presets == ["bogus"]

    def test_unmatched_member_reported(self):
        # 'empty' preset lists 'nomatch' which isn't in the inventory
        res = pm.resolve_disabled(self._cat(), ["empty"], ["basic-memory"])
        assert "nomatch" in res.unmatched_members

    def test_matched_maps_member_to_ids(self):
        inv = ["ida-pro-mcp"]
        res = pm.resolve_disabled(self._cat(), ["re"], inv)
        assert res.matched["ida-pro-mcp"] == ["ida-pro-mcp"]

    def test_fuzzy_member_matches_live_id(self):
        # member stored as short form still resolves against the -mcp live id
        cat = pm.PresetCatalog(core=[], presets={"re": ["ida-pro"]})
        res = pm.resolve_disabled(cat, ["re"], ["ida-pro-mcp"])
        assert res.to_enable == ["ida-pro-mcp"]

    def test_member_in_core_and_preset_deduplicated(self):
        # 'basic-memory' is in core AND in the selected preset, so the second
        # occurrence hits the dedup-skip branch in _collect_enable_members.
        cat = pm.PresetCatalog(
            core=["basic-memory"], presets={"dup": ["basic-memory", "docker"]}
        )
        inv = ["basic-memory", "docker"]
        res = pm.resolve_disabled(cat, ["dup"], inv)
        assert set(res.to_enable) == {"basic-memory", "docker"}
        assert res.to_disable == []


# ── apply_selection ───────────────────────────────────────────────────────────


class TestApplySelection:
    def _claude_json(self, tmp_path: Path, disabled: list[str]) -> Path:
        proj = "C:/proj"
        cj = tmp_path / ".claude.json"
        cj.write_text(
            json.dumps({"projects": {proj: {"disabledMcpServers": disabled}}}),
            encoding="utf-8",
        )
        return cj

    def test_writes_disable_and_enable(self, tmp_path: Path):
        cat = pm.PresetCatalog(core=["basic-memory"], presets={})
        cj = self._claude_json(tmp_path, disabled=["basic-memory"])
        inv = ["basic-memory", "docker"]
        res = pm.apply_selection(
            [], inv, cj, "C:/proj", catalog=cat, backup_dir=tmp_path / "bak"
        )
        data = json.loads(cj.read_text(encoding="utf-8"))
        arr = data["projects"]["C:/proj"]["disabledMcpServers"]
        assert "docker" in arr  # newly disabled
        assert "basic-memory" not in arr  # newly enabled
        assert "docker" in res.newly_disabled
        assert "basic-memory" in res.newly_enabled

    def test_preserves_out_of_inventory_disables(self, tmp_path: Path):
        cat = pm.PresetCatalog(core=["basic-memory"], presets={})
        # a hand-curated disable that is NOT in the live inventory
        cj = self._claude_json(tmp_path, disabled=["claude.ai PubMed"])
        inv = ["basic-memory", "docker"]
        pm.apply_selection(
            [], inv, cj, "C:/proj", catalog=cat, backup_dir=tmp_path / "bak"
        )
        arr = json.loads(cj.read_text(encoding="utf-8"))["projects"]["C:/proj"][
            "disabledMcpServers"
        ]
        assert "claude.ai PubMed" in arr  # untouched
        assert "docker" in arr

    def test_catalog_none_reads_default(self, tmp_path: Path, monkeypatch):
        cat = pm.PresetCatalog(core=["basic-memory"], presets={})
        monkeypatch.setattr(pm, "read_catalog", lambda: cat)
        cj = self._claude_json(tmp_path, disabled=[])
        res = pm.apply_selection(
            [], ["basic-memory"], cj, "C:/proj", backup_dir=tmp_path / "bak"
        )
        assert res.newly_disabled == []

    def test_already_disabled_not_recounted(self, tmp_path: Path):
        # 'docker' is in to_disable but ALREADY disabled, so set_server_disabled
        # returns False and it is not re-counted in newly_disabled (skip branch).
        cat = pm.PresetCatalog(core=["basic-memory"], presets={})
        cj = self._claude_json(tmp_path, disabled=["docker"])
        inv = ["basic-memory", "docker"]
        res = pm.apply_selection(
            [], inv, cj, "C:/proj", catalog=cat, backup_dir=tmp_path / "bak"
        )
        arr = json.loads(cj.read_text(encoding="utf-8"))["projects"]["C:/proj"][
            "disabledMcpServers"
        ]
        assert "docker" in arr  # still disabled
        assert res.newly_disabled == []  # not re-counted
