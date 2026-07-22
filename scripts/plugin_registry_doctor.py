#!/usr/bin/env python3
"""Detect silent corruption and load-blocking defects in the Claude Code plugin harness.

Motivation
----------
On 2026-07-13 a machine freeze left ``~/.claude/plugins/installed_plugins.json``
as 38,989 bytes of pure NUL. NTFS had committed the file's *size* metadata but
never flushed its data extents. Claude Code logged::

    [ERROR] Failed to load installed_plugins.json: JSON Parse error:
            Unrecognized token ' '. Starting with empty state.

and then silently degraded for a week. Nothing in the UI said "your plugin
registry is gone" -- the only symptom the owner saw was an error *count* from
``/reload-plugins`` and a vague sense that things "weren't showing up".

An all-NUL file is invisible to every ordinary check: it exists, it has a
plausible size, ``ls`` looks normal, and a glance at ``wc -c`` says the bytes are
there. Only a byte-level scan finds it. This script is that scan, plus the
adjacent manifest checks that explain a plugin loading with fewer agents or
skills than it advertises.

Read-only. Exits 1 when any finding is reported, 0 when clean, so it can be
wired into a health check.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Directories that hold throwaway clone state; never worth reporting on.
SKIP_DIR_PREFIXES = ("temp_subdir_",)
# ``tool-results`` holds verbatim transcript captures. When an agent inspects a
# corrupt file, the NUL bytes are faithfully recorded there -- a true reading of
# a real problem, but a copy of the evidence rather than the problem itself.
# Scanning it reports the same corruption twice and never yields a fixable path.
SKIP_DIR_NAMES = {".git", "node_modules", "__pycache__", "tool-results"}

# Only text-ish payloads can be judged "corrupt" by a NUL scan; binaries legally
# contain NULs.
TEXT_SUFFIXES = (".json", ".jsonl", ".md", ".yaml", ".yml", ".toml", ".txt")

# A file is flagged when it is entirely NUL, or NUL-dominated past this ratio.
NUL_RATIO_THRESHOLD = 0.30


def _iter_files(root: Path):
    """Walk *root*, pruning throwaway and vendor directories."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in SKIP_DIR_NAMES and not d.startswith(SKIP_DIR_PREFIXES)
        ]
        for name in filenames:
            yield Path(dirpath) / name


def scan_nul_corruption(roots: list[Path]) -> list[dict]:
    """Find text files whose bytes were lost to an unflushed write.

    A crash between metadata commit and data flush leaves the file at full
    length but zero-filled. Reporting the NUL count alongside the size makes the
    diagnosis unambiguous.
    """
    findings: list[dict] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in _iter_files(root):
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            if not raw:
                continue
            nul = raw.count(0)
            if nul == 0:
                continue
            if nul == len(raw):
                kind = "ALL-NUL"
            elif nul > len(raw) * NUL_RATIO_THRESHOLD:
                kind = "MOSTLY-NUL"
            else:
                continue
            findings.append(
                {
                    "check": "nul-corruption",
                    "kind": kind,
                    "path": str(path),
                    "size": len(raw),
                    "nul_bytes": nul,
                }
            )
    return findings


def _has_frontmatter(path: Path) -> bool:
    """True when the file opens with a closed YAML frontmatter block.

    Claude Code discovers agents and skills by reading ``name``/``description``
    out of frontmatter. A markdown file that starts with a heading instead is
    not registered -- it is skipped, and the capability silently never appears.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace").lstrip()
    except OSError:
        return False
    return text.startswith("---") and len(text.split("---", 2)) >= 3


def scan_plugin_cache(cache_root: Path) -> list[dict]:
    """Check every cached ``<marketplace>/<plugin>/<version>`` tree.

    Two defects are load-blocking and otherwise invisible: an agent markdown
    file with no frontmatter, and a skill directory with no ``SKILL.md``.
    """
    findings: list[dict] = []
    if not cache_root.is_dir():
        return findings
    for marketplace in sorted(cache_root.iterdir()):
        if not marketplace.is_dir() or marketplace.name.startswith(SKIP_DIR_PREFIXES):
            continue
        for plugin in sorted(marketplace.iterdir()):
            if not plugin.is_dir():
                continue
            for version in sorted(plugin.iterdir()):
                if not version.is_dir():
                    continue
                tag = f"{plugin.name}@{marketplace.name}:{version.name}"
                findings.extend(_scan_version(version, tag))
    return findings


def _scan_version(version: Path, tag: str) -> list[dict]:
    findings: list[dict] = []
    agents_dir = version / "agents"
    if agents_dir.is_dir():
        for path in sorted(agents_dir.rglob("*.md")):
            if not _has_frontmatter(path):
                findings.append(
                    {
                        "check": "agent-no-frontmatter",
                        "plugin": tag,
                        "path": str(path),
                    }
                )
    skills_dir = version / "skills"
    if skills_dir.is_dir():
        for entry in sorted(skills_dir.iterdir()):
            if not entry.is_dir():
                continue
            skill_md = entry / "SKILL.md"
            if not skill_md.is_file():
                findings.append(
                    {
                        "check": "skill-md-missing",
                        "plugin": tag,
                        "path": str(entry),
                    }
                )
            elif not _has_frontmatter(skill_md):
                findings.append(
                    {
                        "check": "skill-no-frontmatter",
                        "plugin": tag,
                        "path": str(skill_md),
                    }
                )
    return findings


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def scan_orphaned_enabled(settings: Path, known_marketplaces: Path) -> list[dict]:
    """Report ``enabledPlugins`` keys no marketplace catalog can resolve.

    Claude Code logs these as "Skipping orphaned enabledPlugins entry". They are
    harmless individually but accumulate as permanent load-time noise, which is
    what buries a real error in the count.
    """
    findings: list[dict] = []
    settings_data = _load_json(settings)
    known = _load_json(known_marketplaces)
    if not isinstance(settings_data, dict) or not isinstance(known, dict):
        return findings

    catalog: dict[str, set[str]] = {}
    for name, meta in known.items():
        names: set[str] = set()
        location = (meta or {}).get("installLocation")
        if location:
            manifest = Path(location) / ".claude-plugin" / "marketplace.json"
            data = _load_json(manifest)
            if isinstance(data, dict):
                for plugin in data.get("plugins", []):
                    if isinstance(plugin, dict) and plugin.get("name"):
                        names.add(plugin["name"])
                    elif isinstance(plugin, str):
                        names.add(plugin)
        catalog[name] = names

    for key, is_enabled in (settings_data.get("enabledPlugins") or {}).items():
        if "@" not in key:
            findings.append({"check": "malformed-plugin-key", "entry": key})
            continue
        plugin, marketplace = key.rsplit("@", 1)
        if marketplace not in catalog:
            reason = "marketplace-unknown"
        elif plugin not in catalog[marketplace]:
            reason = "not-in-catalog"
        else:
            continue
        findings.append(
            {
                "check": "orphaned-enabled-plugin",
                "entry": key,
                "reason": reason,
                "enabled": bool(is_enabled),
            }
        )
    return findings


def scan_stale_clones(cache_root: Path) -> list[dict]:
    """Measure abandoned ``temp_subdir_*`` marketplace clone directories.

    These are leftovers from interrupted marketplace refreshes. They are not
    load-blocking, but they grow without bound -- worth surfacing as one
    aggregate line rather than hundreds.
    """
    if not cache_root.is_dir():
        return []
    total_bytes = 0
    count = 0
    for entry in cache_root.iterdir():
        if not entry.is_dir() or not entry.name.startswith(SKIP_DIR_PREFIXES):
            continue
        count += 1
        for dirpath, _, filenames in os.walk(entry):
            for name in filenames:
                try:
                    total_bytes += (Path(dirpath) / name).stat().st_size
                except OSError:
                    continue
    if not count:
        return []
    return [
        {
            "check": "stale-marketplace-clones",
            "directories": count,
            "bytes": total_bytes,
            "path": str(cache_root),
        }
    ]


def build_report(claude_home: Path, agents_home: Path) -> list[dict]:
    cache_root = claude_home / "plugins" / "cache"
    return [
        *scan_nul_corruption([claude_home, agents_home]),
        *scan_plugin_cache(cache_root),
        *scan_orphaned_enabled(
            claude_home / "settings.json",
            claude_home / "plugins" / "known_marketplaces.json",
        ),
        *scan_stale_clones(cache_root),
    ]


def _print_human(findings: list[dict]) -> None:
    if not findings:
        print("plugin-registry-doctor: OK (no findings)")
        return
    by_check: dict[str, list[dict]] = {}
    for item in findings:
        by_check.setdefault(item["check"], []).append(item)
    print(f"plugin-registry-doctor: {len(findings)} finding(s)\n")
    for check, items in sorted(by_check.items()):
        print(f"[{check}] {len(items)}")
        for item in items[:20]:
            detail = item.get("path") or item.get("entry") or ""
            extra = ""
            if item["check"] == "nul-corruption":
                extra = f" ({item['kind']} {item['nul_bytes']}/{item['size']} bytes)"
            elif item["check"] == "stale-marketplace-clones":
                mib = item["bytes"] / 1048576
                extra = f" ({item['directories']} dirs, {mib:.1f} MiB)"
            print(f"    {detail}{extra}")
        if len(items) > 20:
            print(f"    ... and {len(items) - 20} more")
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Detect NUL-corrupted harness state and load-blocking plugin "
            "manifest defects. Read-only."
        )
    )
    parser.add_argument(
        "--claude-home",
        type=Path,
        default=Path.home() / ".claude",
        help="Claude Code home (default: ~/.claude)",
    )
    parser.add_argument(
        "--agents-home",
        type=Path,
        default=Path.home() / ".agents",
        help="Shared agent harness home (default: ~/.agents)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON findings.")
    args = parser.parse_args(argv)

    findings = build_report(args.claude_home, args.agents_home)
    if args.json:
        json.dump(findings, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        _print_human(findings)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
