"""Tests for core/status.py — async refresh, merge, graceful degradation."""

import asyncio
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import status as sm  # noqa: E402
from core.models import AuthStatus  # noqa: E402

# ── Fixtures ──────────────────────────────────────────────────────────────────

MCP_LIST = """\
claude.ai Tavily: https://mcp.tavily.com/mcp - ✔ Connected
claude.ai PubMed: https://pubmed.mcp.claude.com/mcp - ✔ Connected
plugin:semgrep:semgrep: semgrep mcp - ✔ Connected
exa: npx exa-mcp  - ✔ Connected
"""

CODEX_JSON = json.dumps(
    [
        {"name": "exa", "enabled": True},
        {"name": "context7", "enabled": True},
        # exa is also in claude-plane above -> cross-plane duplicate
        {"name": "kaggle", "enabled": False},
    ]
)

PROFILES = {
    "profiles": {
        "default": "*ALL*",
        "re": ["binary-ninja-mcp", "ida-pro-mcp"],
        "web": ["firecrawl", "tavily"],
    }
}


def _make_env(tmp_path: Path) -> tuple[Path, Path, Path, Path, str]:
    """Return (claude_json, codex_toml, funnel_profiles, project_path)."""
    cj = tmp_path / ".claude.json"
    proj = str(tmp_path).replace("\\", "/")
    cj.write_text(
        json.dumps({"projects": {proj: {"disabledMcpServers": ["claude.ai PubMed"]}}}),
        encoding="utf-8",
    )

    ct = tmp_path / "codex" / "config.toml"
    ct.parent.mkdir()
    # status module uses json_output injection so toml content doesn't matter here
    ct.write_text("", encoding="utf-8")

    pf = tmp_path / "profiles.json"
    pf.write_text(json.dumps(PROFILES), encoding="utf-8")

    return cj, ct, pf, proj


# ── _merge_rows ────────────────────────────────────────────────────────────────


class TestMergeRows:
    def _make_row(self, id_, plane, enabled=True, status=AuthStatus.UNKNOWN):
        from core.models import ServerRow

        return ServerRow(
            id=id_, name=id_, planes=[plane], enabled=enabled, status=status
        )

    def test_different_ids_not_merged(self):
        a = self._make_row("a", "claude")
        b = self._make_row("b", "codex")
        merged = sm._merge_rows([[a], [b]])
        assert len(merged) == 2

    def test_same_id_merges_planes(self):
        a = self._make_row("shared", "claude")
        b = self._make_row("shared", "codex")
        merged = sm._merge_rows([[a], [b]])
        assert len(merged) == 1
        row = merged[0]
        assert "claude" in row.planes
        assert "codex" in row.planes

    def test_any_disabled_wins(self):
        a = self._make_row("shared", "claude", enabled=True)
        b = self._make_row("shared", "codex", enabled=False)
        merged = sm._merge_rows([[a], [b]])
        assert merged[0].enabled is False

    def test_cross_plane_disabled_keeps_failed_status(self):
        """Pins the MEASURED scope of the `enabled` guard in `ServerRow.dead`.

        A row the claude plane reports FAILED, which ANOTHER plane disables,
        merges to `enabled=False`, so `dead` is False — the predicate half of
        the cross-plane case IS closed.  But `_merge_rows` copies the
        claude-plane `status` verbatim, so it stays FAILED, and both UIs key
        on `row.status.value` rather than on `dead` — the owner still sees
        "error"/red.  This asserts BOTH halves so the docstring cannot drift
        into claiming the rendered status is fixed too.  When the settling
        change lands (re-label FAILED -> DISABLED in `_merge_rows`), update
        THIS test and the `ServerRow.dead` docstring together.
        """
        a = self._make_row("shared", "claude", enabled=True, status=AuthStatus.FAILED)
        b = self._make_row("shared", "codex", enabled=False)
        merged = sm._merge_rows([[a], [b]])
        row = merged[0]
        assert row.enabled is False
        # closed half: the predicate no longer calls it dead
        assert row.dead is False
        # NOT-closed half: the merge leaves the rendered status untouched
        assert row.status == AuthStatus.FAILED

    def test_unknown_status_upgraded(self):
        a = self._make_row("x", "claude", status=AuthStatus.UNKNOWN)
        b = self._make_row("x", "codex", status=AuthStatus.CONNECTED)
        merged = sm._merge_rows([[a], [b]])
        assert merged[0].status == AuthStatus.CONNECTED

    def test_sorted_by_id(self):
        rows = [
            self._make_row("z", "claude"),
            self._make_row("a", "claude"),
            self._make_row("m", "claude"),
        ]
        merged = sm._merge_rows([rows])
        ids = [r.id for r in merged]
        assert ids == sorted(ids)


# ── refresh (async) ────────────────────────────────────────────────────────────


class TestRefresh:
    def test_returns_merged_rows(self, tmp_path: Path):
        cj, ct, pf, proj = _make_env(tmp_path)
        rows = asyncio.run(
            sm.refresh(
                claude_json=cj,
                codex_toml=ct,
                funnel_profiles=pf,
                project_path=proj,
                mcp_list_output=MCP_LIST,
                codex_json_output=CODEX_JSON,
            )
        )
        ids = {r.id for r in rows}
        # claude-plane servers
        assert "claude.ai Tavily" in ids
        assert "plugin:semgrep:semgrep" in ids
        # codex-plane servers
        assert "exa" in ids
        # funnel-plane servers (from non-default profiles)
        assert "binary-ninja-mcp" in ids

    def test_disabled_server_is_disabled(self, tmp_path: Path):
        cj, ct, pf, proj = _make_env(tmp_path)
        rows = asyncio.run(
            sm.refresh(
                claude_json=cj,
                codex_toml=ct,
                funnel_profiles=pf,
                project_path=proj,
                mcp_list_output=MCP_LIST,
                codex_json_output=CODEX_JSON,
            )
        )
        by_id = {r.id: r for r in rows}
        assert by_id["claude.ai PubMed"].enabled is False

    def test_cross_plane_duplicate_flagged(self, tmp_path: Path):
        cj, ct, pf, proj = _make_env(tmp_path)
        rows = asyncio.run(
            sm.refresh(
                claude_json=cj,
                codex_toml=ct,
                funnel_profiles=pf,
                project_path=proj,
                mcp_list_output=MCP_LIST,
                codex_json_output=CODEX_JSON,
            )
        )
        by_id = {r.id: r for r in rows}
        # 'exa' is in both the claude-plane MCP_LIST and codex CODEX_JSON
        assert by_id["exa"].duplicated is True
        assert "claude" in by_id["exa"].planes
        assert "codex" in by_id["exa"].planes

    def test_graceful_when_claude_json_missing(self, tmp_path: Path):
        # Should not raise even if claude.json is absent
        rows = asyncio.run(
            sm.refresh(
                claude_json=tmp_path / "nope.json",
                codex_toml=tmp_path / "nope.toml",
                funnel_profiles=tmp_path / "nope2.json",
                project_path="C:/x",
                mcp_list_output="",
                codex_json_output="[]",
            )
        )
        assert isinstance(rows, list)

    def test_no_duplicates_within_plane(self, tmp_path: Path):
        cj, ct, pf, proj = _make_env(tmp_path)
        rows = asyncio.run(
            sm.refresh(
                claude_json=cj,
                codex_toml=ct,
                funnel_profiles=pf,
                project_path=proj,
                mcp_list_output=MCP_LIST,
                codex_json_output=CODEX_JSON,
            )
        )
        ids = [r.id for r in rows]
        assert len(ids) == len(set(ids))


# ── refresh_sync ───────────────────────────────────────────────────────────────


class TestRefreshSync:
    def test_sync_wrapper_returns_same_results(self, tmp_path: Path):
        cj, ct, pf, proj = _make_env(tmp_path)
        rows = sm.refresh_sync(
            claude_json=cj,
            codex_toml=ct,
            funnel_profiles=pf,
            project_path=proj,
            mcp_list_output=MCP_LIST,
            codex_json_output=CODEX_JSON,
        )
        assert any(r.id == "claude.ai Tavily" for r in rows)
