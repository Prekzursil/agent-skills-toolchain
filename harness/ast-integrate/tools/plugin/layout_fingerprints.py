#!/usr/bin/env python3
"""Discriminating fingerprints for historical on-disk plugin layouts.

The migration engine (IMP-0047) must select a step chain from measured estate
shape, not from a version string that may be absent or spoofed.

Each fingerprint requires TWO independent signals:
  1. a marker file exists
  2. a second discriminating property (key location or directory shape)

A single marker is insufficient: several layouts on this estate share marker
filenames while differing in which FILE holds the live key
(disabledMcpServers at ~/.claude.json root is inert; the live map is
per-project. enabledPlugins lives in ~/.claude/settings.json, not the
claude.json root. .mcp.json at $HOME is not the per-project live file).

Ambiguity is a first-class result. A tree matching two fingerprints is
reported as AMBIGUOUS and never silently resolved to one chain.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

COPIED_SKILLS = "pre-marketplace-copied-skills"
PER_PROJECT_MCP = "per-project-mcp-json"
ROOT_DISABLED_MCP = "root-scoped-disabledMcpServers"
PRE_DISPATCH_HOOKS = "pre-dispatch-hooks"

FINGERPRINT_IDS = (
    COPIED_SKILLS,
    PER_PROJECT_MCP,
    ROOT_DISABLED_MCP,
    PRE_DISPATCH_HOOKS,
)

STEP_CHAINS: dict[str, tuple[str, ...]] = {
    COPIED_SKILLS: ("copied-skills-to-marketplace",),
    PER_PROJECT_MCP: ("mcp-json-to-project-block",),
    ROOT_DISABLED_MCP: ("disabledMcpServers-root-to-per-project",),
    PRE_DISPATCH_HOOKS: ("hooks-to-dispatch-manifest",),
}

STATUS_NONE = "NONE"
STATUS_UNIQUE = "UNIQUE"
STATUS_AMBIGUOUS = "AMBIGUOUS"


def split_estate(root: Path) -> tuple[Path, Path]:
    """Return (home, project). Split trees use home/ and project/ children."""
    root = Path(root)
    home = root / "home" if (root / "home").is_dir() else root
    project = root / "project" if (root / "project").is_dir() else root
    return home, project


def load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


@dataclass(frozen=True)
class Signal:
    kind: str
    path: str
    detail: str
    present: bool

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "path": self.path,
            "detail": self.detail,
            "present": self.present,
        }


@dataclass(frozen=True)
class FingerprintEval:
    fingerprint_id: str
    step_chain: tuple[str, ...]
    marker: Signal
    discriminator: Signal

    @property
    def matched(self) -> bool:
        return self.marker.present and self.discriminator.present

    def to_dict(self) -> dict:
        return {
            "id": self.fingerprint_id,
            "matched": self.matched,
            "step_chain": list(self.step_chain),
            "signals": [self.marker.to_dict(), self.discriminator.to_dict()],
        }


def _copied_skills_marker(home: Path, _project: Path) -> Signal:
    skills = home / ".claude" / "skills"
    found: list[str] = []
    if skills.is_dir():
        for child in sorted(skills.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.is_file():
                found.append(skill_md.as_posix())
    return Signal(
        kind="marker-file",
        path=(skills / "*/SKILL.md").as_posix(),
        detail=(
            f"copied skill trees={len(found)} first={found[0]}"
            if found
            else "no home/.claude/skills/*/SKILL.md"
        ),
        present=bool(found),
    )


def _marketplace_paths(home: Path, project: Path) -> list[Path]:
    return [
        project / ".claude-plugin" / "marketplace.json",
        home / ".claude-plugin" / "marketplace.json",
        home / ".claude" / "plugins" / "marketplace.json",
    ]


def _copied_skills_discriminator(home: Path, project: Path) -> Signal:
    """Pre-marketplace: no marketplace manifest and no live enabledPlugins.

    enabledPlugins is read from ~/.claude/settings.json only. The same key at
    ~/.claude.json root is inert on this estate and does not suppress the hit.
    """
    marketplaces = [p for p in _marketplace_paths(home, project) if p.is_file()]
    settings_path = home / ".claude" / "settings.json"
    settings = load_json(settings_path) or {}
    enabled = settings.get("enabledPlugins")
    live_enabled = isinstance(enabled, dict) and len(enabled) > 0
    present = (not marketplaces) and (not live_enabled)
    if marketplaces:
        detail = f"marketplace present at {marketplaces[0].as_posix()}"
    elif live_enabled:
        detail = f"enabledPlugins live in {settings_path.as_posix()}"
    else:
        detail = (
            "no marketplace.json and no enabledPlugins in "
            "home/.claude/settings.json"
        )
    return Signal(
        kind="directory-shape",
        path="home/.claude/settings.json+marketplace.json",
        detail=detail,
        present=present,
    )


def _mcp_marker(_home: Path, project: Path) -> Signal:
    path = project / ".mcp.json"
    return Signal(
        kind="marker-file",
        path=path.as_posix(),
        detail="project/.mcp.json exists" if path.is_file() else "project/.mcp.json absent",
        present=path.is_file(),
    )


def _mcp_discriminator(_home: Path, project: Path) -> Signal:
    """Live key is mcpServers inside the per-project .mcp.json.

    ~/.mcp.json (home) sharing the same filename is a different file and does
    not satisfy this fingerprint.
    """
    path = project / ".mcp.json"
    doc = load_json(path)
    servers = doc.get("mcpServers") if isinstance(doc, dict) else None
    live = isinstance(servers, dict) and len(servers) > 0
    return Signal(
        kind="key-location",
        path=path.as_posix(),
        detail=(
            f"mcpServers keys={sorted(servers)}"
            if live
            else "mcpServers absent or empty in project/.mcp.json"
        ),
        present=live,
    )


def _root_disabled_marker(home: Path, _project: Path) -> Signal:
    path = home / ".claude.json"
    return Signal(
        kind="marker-file",
        path=path.as_posix(),
        detail="home/.claude.json exists" if path.is_file() else "home/.claude.json absent",
        present=path.is_file(),
    )


def _root_disabled_discriminator(home: Path, _project: Path) -> Signal:
    """Live-looking key at ROOT of ~/.claude.json is the legacy inert layout.

    Current layout keeps disabledMcpServers under projects.<path> only. The
    marker filename is shared; the key location discriminates.
    """
    path = home / ".claude.json"
    doc = load_json(path)
    at_root = isinstance(doc, dict) and "disabledMcpServers" in doc
    return Signal(
        kind="key-location",
        path=path.as_posix() + "#/disabledMcpServers",
        detail=(
            "disabledMcpServers at ~/.claude.json ROOT (inert on this estate)"
            if at_root
            else "disabledMcpServers not at ~/.claude.json root"
        ),
        present=at_root,
    )


def _hook_files(hooks_root: Path) -> list[Path]:
    if not hooks_root.is_dir():
        return []
    found: list[Path] = []
    for path in sorted(hooks_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(hooks_root).as_posix()
        if rel == "_dispatch/manifest.json":
            continue
        found.append(path)
    return found


def _pre_dispatch_marker(home: Path, _project: Path) -> Signal:
    hooks_root = home / ".claude" / "hooks"
    files = _hook_files(hooks_root)
    settings = load_json(home / ".claude" / "settings.json") or {}
    settings_hooks = "hooks" in settings
    present = bool(files) or settings_hooks
    if files:
        detail = f"standalone hook files={len(files)} first={files[0].as_posix()}"
    elif settings_hooks:
        detail = "hooks key present in home/.claude/settings.json"
    else:
        detail = "no standalone hook files and no settings.hooks"
    return Signal(
        kind="marker-file",
        path=(hooks_root / "*").as_posix(),
        detail=detail,
        present=present,
    )


def _pre_dispatch_discriminator(home: Path, _project: Path) -> Signal:
    manifest = home / ".claude" / "hooks" / "_dispatch" / "manifest.json"
    present = not manifest.is_file()
    return Signal(
        kind="directory-shape",
        path=manifest.as_posix(),
        detail=(
            "hooks/_dispatch/manifest.json absent (pre-dispatch)"
            if present
            else "hooks/_dispatch/manifest.json present (current dispatch layout)"
        ),
        present=present,
    )


@dataclass(frozen=True)
class FingerprintSpec:
    fingerprint_id: str
    marker: Callable[[Path, Path], Signal]
    discriminator: Callable[[Path, Path], Signal]

    @property
    def step_chain(self) -> tuple[str, ...]:
        return STEP_CHAINS[self.fingerprint_id]


SPECS: tuple[FingerprintSpec, ...] = (
    FingerprintSpec(COPIED_SKILLS, _copied_skills_marker, _copied_skills_discriminator),
    FingerprintSpec(PER_PROJECT_MCP, _mcp_marker, _mcp_discriminator),
    FingerprintSpec(ROOT_DISABLED_MCP, _root_disabled_marker, _root_disabled_discriminator),
    FingerprintSpec(PRE_DISPATCH_HOOKS, _pre_dispatch_marker, _pre_dispatch_discriminator),
)


def inspect(estate_root: Path) -> list[FingerprintEval]:
    home, project = split_estate(Path(estate_root))
    rows: list[FingerprintEval] = []
    for spec in SPECS:
        rows.append(
            FingerprintEval(
                fingerprint_id=spec.fingerprint_id,
                step_chain=spec.step_chain,
                marker=spec.marker(home, project),
                discriminator=spec.discriminator(home, project),
            )
        )
    return rows


def classify(estate_root: Path | str) -> dict:
    """Public detector. Never consults a version string."""
    root = Path(estate_root)
    rows = inspect(root)
    matches = [row for row in rows if row.matched]
    if not matches:
        status = STATUS_NONE
        selected = None
        chain: list[str] = []
    elif len(matches) == 1:
        status = STATUS_UNIQUE
        selected = matches[0].fingerprint_id
        chain = list(matches[0].step_chain)
    else:
        status = STATUS_AMBIGUOUS
        selected = None
        chain = []
    return {
        "status": status,
        "selected": selected,
        "step_chain": chain,
        "match_ids": [row.fingerprint_id for row in matches],
        "match_count": len(matches),
        "fingerprints": [row.to_dict() for row in rows],
        "version_string_ignored": True,
        "estate_root": str(root),
    }


def step_chain_for(result: dict) -> list[str]:
    """Engine entry: empty unless the match is unique. Never guesses."""
    if result.get("status") != STATUS_UNIQUE:
        return []
    return list(result.get("step_chain") or [])


def main(argv: Iterable[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: layout_fingerprints.py <estate-root> [...]", file=sys.stderr)
        return 2
    for raw in args:
        print(json.dumps(classify(raw), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
