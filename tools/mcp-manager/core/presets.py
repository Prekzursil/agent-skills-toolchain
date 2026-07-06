"""Named preset store (ENABLE-list semantics) for the Claude plane.

A *preset* is a named list of servers to ENABLE.  Presets compose (union), and
``core`` is an always-on set folded into every apply.  The resolver inverts the
enable-set against the LIVE inventory to compute the per-project disable-list:

    disabled = all_known_inventory - (core union selected_presets)

Storage: ``~/.mcp-presets.json`` (created on first use if absent).  File shape::

    {
        "_comment": "...",
        "core": ["basic-memory", "tavily", ...],
        "presets": {"re": ["ida-pro-mcp", ...], "chem": [...], ...}
    }

HARD CONSTRAINTS honoured here:
- Applying a preset only ever writes ``projects[path].disabledMcpServers`` via
  ``core.claude_adapter.set_server_disabled`` (mtime-merge + timestamped backup).
  Top-level user-scope ``mcpServers`` is never touched.
- The resolver only enables/disables servers that appear in the supplied LIVE
  inventory.  Disabled entries for servers OUTSIDE the inventory (the user's
  hand-curated ``claude.ai *`` / ``plugin:*`` disables) are never removed.
- Config edits take effect the NEXT session — callers must message
  "applies next session — restart to take effect"; nothing here is live.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

_PRESETS_PATH = Path.home() / ".mcp-presets.json"

# Always-on core set (spec 3a).  Stored as exact live server names so the
# resolver matches the real inventory precisely.
SEED_CORE: list[str] = [
    "basic-memory",
    "tavily",
    "exa",
    "context7",
    "github_cli",
    "deepwiki",
    "huggingface",
    "figma",
]

# Seven composable bundles (spec 3a).  Spec abbreviations are mapped to the
# exact live inventory server names (e.g. ida -> ida-pro-mcp) so resolution is
# exact and predictable; the fuzzy matcher below is a robustness fallback only.
SEED_PRESETS: dict[str, list[str]] = {
    "re": [
        "ida-pro-mcp",
        "ghidra-mcp",
        "binary-ninja-mcp",
        "frida-mcp",
        "cheatengine",
        "apktool-mcp",
        "jadx-mcp",
        "hexstrike-ai",
        "cve-mcp",
    ],
    "chem": [
        "rdkit",
        "schrodinger",
        "qdx-rush",
        "openmm-md",
        "tooluniverse",
        "paper-search",
        "scholarly-access",
    ],
    "research": [
        "firecrawl",
        "perplexity",
        "searxng",
        "markitdown",
        "paper-search",
    ],
    "social": ["social-hub"],
    "cloud": ["cloud-hub", "docker", "gitlab", "ralph-orchestrator"],
    "media": ["elevenlabs", "playwright", "chrome-devtools"],
    "docs": ["excel", "pdf-reader", "ocr-suite", "repomix", "qlty"],
}

_CORE_KEY = "core"
_PRESETS_KEY = "presets"


# ── models ────────────────────────────────────────────────────────────────────


@dataclass
class PresetCatalog:
    """The full named-preset catalog (core + named bundles)."""

    core: list[str] = field(default_factory=list)
    presets: dict[str, list[str]] = field(default_factory=dict)
    raw: dict[str, object] = field(default_factory=dict)

    def names(self) -> list[str]:
        """Selectable preset names (does not include the implicit 'core')."""
        return sorted(self.presets.keys())

    def members(self, name: str) -> list[str] | None:
        """Enable-list for a named preset, or None if it doesn't exist.

        The reserved name 'core' resolves to the always-on core set.
        """
        if name == _CORE_KEY:
            return list(self.core)
        members = self.presets.get(name)
        return list(members) if members is not None else None


@dataclass
class ResolveResult:
    """Outcome of resolving a selection against a live inventory."""

    to_disable: list[str]  # inventory ids that should be disabled
    to_enable: list[str]  # inventory ids that should stay/become enabled
    matched: dict[str, list[str]]  # member -> [inventory ids it matched]
    unmatched_members: list[str]  # enable members with no inventory match
    unknown_presets: list[str]  # selected names not present in the catalog


@dataclass
class ApplyResult:
    """Outcome of applying a selection to a project's disable-list."""

    resolve: ResolveResult
    newly_disabled: list[str]  # ids actually written to disabled
    newly_enabled: list[str]  # ids actually removed from disabled


# ── normalisation / matching ──────────────────────────────────────────────────


def normalize_id(value: str) -> str:
    """Collapse a server id/name to a comparable token key.

    Strips the ``claude.ai `` connector prefix and ``plugin:ns:`` namespace,
    lowercases, drops a leading/trailing generic ``mcp`` marker token, and
    concatenates the remaining alphanumeric tokens.  Used for EXACT membership
    matching in the resolver (predictable — no partial/substring surprises).
    """
    s = value.strip().lower()
    if s.startswith("claude.ai "):
        s = s[len("claude.ai ") :]
    if s.startswith("plugin:"):
        s = s.split(":")[-1]
    toks = [t for t in re.split(r"[^a-z0-9]+", s) if t]
    if len(toks) > 1 and toks[-1] == "mcp":
        toks = toks[:-1]
    if len(toks) > 1 and toks[0] == "mcp":
        toks = toks[1:]
    return "".join(toks)


def fuzzy_filter(query: str, items: list[str]) -> list[str]:
    """Return items matching ``query`` as an ordered subsequence (for the UI
    search box).  Case-insensitive; empty query returns all items unchanged.

    This is a DISPLAY filter only — it never feeds the disable computation.
    """
    q = query.strip().lower()
    if not q:
        return list(items)
    q_compact = re.sub(r"[^a-z0-9]+", "", q)
    out: list[str] = []
    for item in items:
        hay = item.lower()
        if q in hay:
            out.append(item)
            continue
        if q_compact and _is_subsequence(q_compact, re.sub(r"[^a-z0-9]+", "", hay)):
            out.append(item)
    return out


def _is_subsequence(needle: str, haystack: str) -> bool:
    it = iter(haystack)
    return all(ch in it for ch in needle)


# ── file io ───────────────────────────────────────────────────────────────────


def default_catalog() -> PresetCatalog:
    """Return the seeded catalog (spec 3a) as an in-memory object."""
    return PresetCatalog(
        core=list(SEED_CORE),
        presets={k: list(v) for k, v in SEED_PRESETS.items()},
        raw={
            "_comment": (
                "mcp-manager named presets. Each preset lists servers to ENABLE. "
                "'core' is always on. Applying a preset writes the current "
                "project's disabledMcpServers and takes effect NEXT session."
            ),
        },
    )


def _load_raw(path: Path) -> dict[str, object] | None:
    try:
        return cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def read_catalog(path: Path = _PRESETS_PATH) -> PresetCatalog:
    """Read the catalog, falling back to the seed if missing/malformed.

    Does NOT write anything (fail-open read).  Use ``ensure_catalog_file`` to
    materialise the seed on disk.
    """
    raw = _load_raw(path)
    if raw is None:
        return default_catalog()
    core_val = raw.get(_CORE_KEY)
    core = list(cast("list[str]", core_val)) if isinstance(core_val, list) else []
    presets: dict[str, list[str]] = {}
    presets_val = raw.get(_PRESETS_KEY)
    if isinstance(presets_val, dict):
        for name, members in cast("dict[str, object]", presets_val).items():
            if isinstance(members, list):
                presets[name] = [str(m) for m in cast("list[object]", members)]
    return PresetCatalog(core=core, presets=presets, raw=raw)


def _backup(path: Path) -> Path:
    bak_dir = path.parent / ".mcp-manager-backups"
    bak_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    bak = bak_dir / f"{path.name}.{ts}.bak"
    _ = shutil.copy2(path, bak)
    return bak


def write_catalog(
    catalog: PresetCatalog,
    path: Path = _PRESETS_PATH,
    *,
    backup: bool = True,
) -> None:
    """Persist the catalog, preserving any unknown top-level keys."""
    raw = _load_raw(path) or {}
    # keep hand-edited extras (e.g. _comment) but seed a comment if none exists
    for k, v in catalog.raw.items():
        raw.setdefault(k, v)
    if backup and path.exists():
        _ = _backup(path)
    raw[_CORE_KEY] = list(catalog.core)
    raw[_PRESETS_KEY] = {k: list(v) for k, v in catalog.presets.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")


def ensure_catalog_file(path: Path = _PRESETS_PATH) -> PresetCatalog:
    """Create the seeded catalog file if absent; return the on-disk catalog."""
    if not path.exists():
        write_catalog(default_catalog(), path, backup=False)
    return read_catalog(path)


def save_preset(
    name: str,
    members: list[str],
    path: Path = _PRESETS_PATH,
    *,
    backup: bool = True,
) -> bool:
    """Create or overwrite a named preset. Returns True if the catalog changed."""
    catalog = read_catalog(path)
    existing = catalog.presets.get(name)
    new_members = list(members)
    if existing == new_members:
        return False
    catalog.presets[name] = new_members
    write_catalog(catalog, path, backup=backup)
    return True


def delete_preset(
    name: str,
    path: Path = _PRESETS_PATH,
    *,
    backup: bool = True,
) -> bool:
    """Remove a named preset. Returns True if it existed and was removed."""
    catalog = read_catalog(path)
    if name not in catalog.presets:
        return False
    del catalog.presets[name]
    write_catalog(catalog, path, backup=backup)
    return True


# ── resolver ──────────────────────────────────────────────────────────────────


def _collect_enable_members(
    catalog: PresetCatalog, selected: list[str]
) -> tuple[list[str], list[str]]:
    """Return (enable_members, unknown_presets) for a selection.

    'core' is always folded in.  Duplicate members are de-duplicated while
    preserving first-seen order.
    """
    members: list[str] = []
    seen: set[str] = set()

    def _add(items: list[str]) -> None:
        for m in items:
            if m not in seen:
                seen.add(m)
                members.append(m)

    _add(catalog.core)
    unknown: list[str] = []
    for name in selected:
        if name == _CORE_KEY:
            continue  # core already folded in
        preset = catalog.presets.get(name)
        if preset is None:
            unknown.append(name)
            continue
        _add(preset)
    return members, unknown


def resolve_disabled(
    catalog: PresetCatalog,
    selected: list[str],
    inventory_ids: list[str],
) -> ResolveResult:
    """Compute which inventory servers to disable/enable for a selection.

    ``disabled = inventory - {servers matching any enable member}``.

    Matching is EXACT on the normalized token key (see ``normalize_id``), so a
    server is only kept enabled when it truly corresponds to a listed member.
    """
    enable_members, unknown = _collect_enable_members(catalog, selected)
    member_norm = {m: normalize_id(m) for m in enable_members}
    enabled_norms = set(member_norm.values())

    matched: dict[str, list[str]] = {m: [] for m in enable_members}
    to_disable: list[str] = []
    to_enable: list[str] = []
    for sid in inventory_ids:
        norm = normalize_id(sid)
        if norm in enabled_norms:
            to_enable.append(sid)
            for m, mn in member_norm.items():
                if mn == norm:
                    matched[m].append(sid)
        else:
            to_disable.append(sid)

    unmatched = [m for m in enable_members if not matched[m]]
    return ResolveResult(
        to_disable=to_disable,
        to_enable=to_enable,
        matched=matched,
        unmatched_members=unmatched,
        unknown_presets=unknown,
    )


def apply_selection(
    selected: list[str],
    inventory_ids: list[str],
    claude_json: Path,
    project_path: str,
    *,
    catalog: PresetCatalog | None = None,
    backup_dir: Path | None = None,
) -> ApplyResult:
    """Resolve a selection and write the disable-list for one project.

    Only servers present in ``inventory_ids`` are touched; disabled entries for
    servers outside the inventory (hand-curated claude.ai/plugin disables) are
    preserved.  Uses the safe mtime-merge write path.  Takes effect NEXT session.
    """
    from . import claude_adapter  # deferred to avoid import cycle

    if catalog is None:
        catalog = read_catalog()
    res = resolve_disabled(catalog, selected, inventory_ids)

    newly_disabled: list[str] = []
    newly_enabled: list[str] = []
    for sid in res.to_disable:
        if claude_adapter.set_server_disabled(
            claude_json,
            project_path,
            sid,
            True,
            backup_dir=backup_dir,
            _mtime_check=False,
        ):
            newly_disabled.append(sid)
    for sid in res.to_enable:
        if claude_adapter.set_server_disabled(
            claude_json,
            project_path,
            sid,
            False,
            backup_dir=backup_dir,
            _mtime_check=False,
        ):
            newly_enabled.append(sid)
    return ApplyResult(
        resolve=res, newly_disabled=newly_disabled, newly_enabled=newly_enabled
    )
