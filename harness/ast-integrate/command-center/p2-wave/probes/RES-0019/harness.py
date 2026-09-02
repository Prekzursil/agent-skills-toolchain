#!/usr/bin/env python3
"""Throwaway --settings home + marketplace-root skill loader for RES-0019.

Two independent live signals (catalog evidence_requirement):
  (a) the client's loaded-skill report at .res0019-runtime/loaded-skills.json
  (b) a filesystem walk counting skills/*/SKILL.md
settings.json / file presence are claims, never either signal.

Replace-semantics (code.claude.com plugins-reference Path behavior rules):
  skills normally ADD to the default skills/ scan, EXCEPT when a marketplace
  entry's source resolves to the marketplace root: declaring specific
  subdirectories REPLACES the default skills/ scan.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_NAME = "res0019-fork-plugin"
MARKETPLACE_NAME = "res0019-teardown-canary"
ON_DISK = 222
DECLARED = 110
COMMAND_SIBLINGS = 24
FIXTURE_NAME = "res0019-fixture-visible"
DEV_MARKERS = (
    ".claude/settings.json",
    ".claude/skills/live-marker/SKILL.md",
    ".claude/plugins/live-plugin/plugin.json",
    "AppData/Roaming/Claude/claude.json",
)


class IsolationError(RuntimeError):
    pass


def skill_id(i: int) -> str:
    return f"s{i:03d}"


def declared_relpaths() -> list[str]:
    return [f"./skills/{skill_id(i)}" for i in range(DECLARED)] + [
        f"./skills/{FIXTURE_NAME}"
    ]


def windows_env(profile: Path) -> dict[str, str]:
    env = os.environ.copy()
    profile = profile.resolve()
    env["USERPROFILE"] = str(profile)
    env["HOME"] = str(profile)
    env["CLAUDE_CONFIG_DIR"] = str(profile / ".claude")
    env["HOMEDRIVE"] = "C:"
    env["HOMEPATH"] = "\\Users\\" + profile.name
    env["APPDATA"] = str(profile / "AppData" / "Roaming")
    env["LOCALAPPDATA"] = str(profile / "AppData" / "Local")
    env["USERNAME"] = profile.name
    env["USER"] = profile.name
    return env


def assert_isolated(profile: Path) -> None:
    real = Path.home().resolve()
    got = profile.resolve()
    if got == real:
        raise IsolationError(f"profile equals host HOME: {got}")
    if real in got.parents:
        raise IsolationError(f"profile nested under host HOME: {got}")
    if got in real.parents:
        raise IsolationError(f"profile is an ancestor of host HOME: {got}")


def make_fresh_profile(root: Path, name: str = "res0019-fresh") -> Path:
    profile = root / "Users" / name
    if profile.exists():
        shutil.rmtree(profile)
    (profile / "AppData" / "Roaming").mkdir(parents=True)
    (profile / "AppData" / "Local").mkdir(parents=True)
    assert_isolated(profile)
    return profile


def plant_developer_profile(root: Path) -> Path:
    dev = root / "Users" / "developer-loaded"
    if dev.exists():
        shutil.rmtree(dev)
    for rel in DEV_MARKERS:
        path = dev / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"developer-harness {rel}\n", encoding="utf-8")
    return dev


def contamination(profile: Path) -> list[str]:
    return [rel for rel in DEV_MARKERS if (profile / rel).exists()]


def plugin_dir(profile: Path) -> Path:
    return profile / ".claude" / "plugins" / PLUGIN_NAME


def settings_path(profile: Path) -> Path:
    return profile / ".claude" / "settings.json"


def inventory_path(profile: Path) -> Path:
    return profile / ".res0019-runtime" / "loaded-skills.json"


def live_home() -> Path:
    return Path.home().resolve()


def live_skill_census(home: Path | None = None) -> dict:
    """Read-only census of the live profile. Never writes."""
    home = (home or live_home()).resolve()
    roots = [
        home / ".claude" / "skills",
        home / ".claude" / "plugins",
        home / ".agents" / "skills",
    ]
    files: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("SKILL.md")):
            if path.is_file():
                files.append(path.relative_to(home).as_posix())
    blob = "\n".join(files).encode("utf-8")
    return {
        "home": str(home),
        "count": len(files),
        "paths": files,
        "sha256": hashlib.sha256(blob).hexdigest(),
    }


def _write_skill(dest: Path, name: str, body: str) -> None:
    folder = dest / "skills" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\n---\n\n# {name}\n\n{body}\n",
        encoding="utf-8",
    )


def generate_plugin_tree(dest: Path) -> dict:
    """Materialize the 222/110/136/24 teardown split inside dest."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for i in range(ON_DISK):
        _write_skill(
            dest,
            skill_id(i),
            "Packaged skill file for the 110/222 replace-semantics fork.",
        )
    _write_skill(
        dest,
        FIXTURE_NAME,
        "Uniquely-named detector-control skill. The loaded-skill listing must show this name.",
    )
    commands = dest / "commands"
    commands.mkdir(parents=True, exist_ok=True)
    for i in range(COMMAND_SIBLINGS):
        (commands / f"c{i:02d}.md").write_text(
            f"# command-c{i:02d}\nNot a skill. Sibling file in the 24-count column.\n",
            encoding="utf-8",
        )
    skills_field = declared_relpaths()
    marketplace = {
        "name": MARKETPLACE_NAME,
        "owner": {"name": "res0019"},
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": ".",
                "description": "Marketplace-root source: skills[] replaces default scan.",
                "skills": skills_field,
            }
        ],
    }
    plugin_json = {
        "name": PLUGIN_NAME,
        "version": "0.0.1-res0019",
        "description": "RES-0019 222-on-disk / 110-declared marketplace-root canary.",
    }
    meta = dest / ".claude-plugin"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "marketplace.json").write_text(
        json.dumps(marketplace, indent=2) + "\n", encoding="utf-8"
    )
    (meta / "plugin.json").write_text(
        json.dumps(plugin_json, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "plugin_dir": str(dest),
        "on_disk": ON_DISK,
        "declared": DECLARED,
        "command_siblings": COMMAND_SIBLINGS,
        "fixture": FIXTURE_NAME,
        "skills_field": skills_field,
    }


def marketplace_entry(plugin_root: Path) -> dict:
    path = plugin_root / ".claude-plugin" / "marketplace.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    plugins = doc.get("plugins") or []
    if not plugins:
        raise IsolationError("marketplace.json has no plugins")
    return plugins[0]


def source_is_marketplace_root(entry: dict) -> bool:
    source = entry.get("source")
    if source in {".", "./", ""}:
        return True
    if isinstance(source, dict):
        return str(source.get("path") or "") in {".", "./", ""}
    return False


def parse_skill_name(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for line in text[3:end].splitlines():
                if line.startswith("name:"):
                    return line.split(":", 1)[1].strip()
    return skill_md.parent.name


def filesystem_skill_files(plugin_root: Path) -> list[str]:
    files: list[str] = []
    skills = plugin_root / "skills"
    if not skills.is_dir():
        return files
    for path in sorted(skills.glob("*/SKILL.md")):
        if path.is_file():
            files.append(path.relative_to(plugin_root).as_posix())
    return files


def filesystem_skill_count(plugin_root: Path) -> int:
    return len(filesystem_skill_files(plugin_root))


def _resolve_declared(plugin_root: Path, rel: str) -> Path | None:
    rel = rel.replace("\\", "/").strip()
    if not rel.startswith("./"):
        rel = "./" + rel.lstrip("/")
    path = (plugin_root / rel[2:]).resolve()
    try:
        path.relative_to(plugin_root.resolve())
    except ValueError:
        return None
    if path.is_dir():
        md = path / "SKILL.md"
        return md if md.is_file() else None
    if path.name == "SKILL.md" and path.is_file():
        return path
    return None


def load_client_skills(plugin_root: Path, *, replace: bool | None = None) -> dict:
    """Client loaded-skill report. replace=None follows the marketplace-root rule."""
    entry = marketplace_entry(plugin_root)
    skills_field = list(entry.get("skills") or [])
    root_source = source_is_marketplace_root(entry)
    if replace is None:
        replace = bool(root_source and skills_field)
    default_files = [
        plugin_root / rel for rel in filesystem_skill_files(plugin_root)
    ]
    if replace:
        loaded_files: list[Path] = []
        for rel in skills_field:
            md = _resolve_declared(plugin_root, rel)
            if md is not None:
                loaded_files.append(md)
        mode = "replace"
    else:
        loaded_files = list(default_files)
        mode = "union-default-scan"
        for rel in skills_field:
            md = _resolve_declared(plugin_root, rel)
            if md is not None and md not in loaded_files:
                loaded_files.append(md)
                mode = "union-default-plus-declared"
    by_name: dict[str, dict] = {}
    for md in loaded_files:
        name = parse_skill_name(md)
        by_name[name] = {
            "name": name,
            "path": md.relative_to(plugin_root).as_posix(),
        }
    names = sorted(by_name)
    return {
        "loaded_count": len(by_name),
        "loaded_names": names,
        "mode": mode,
        "replace": replace,
        "root_source": root_source,
        "declared_field_count": len(skills_field),
        "fixture_visible": FIXTURE_NAME in by_name,
        "plugin_body_count": len([n for n in names if n != FIXTURE_NAME]),
    }


def write_inventory(profile: Path, report: dict) -> None:
    path = inventory_path(profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def read_inventory(profile: Path) -> dict:
    path = inventory_path(profile)
    if not path.is_file():
        return {
            "loaded_count": 0,
            "loaded_names": [],
            "fixture_visible": False,
            "plugin_body_count": 0,
            "mode": "absent",
        }
    return json.loads(path.read_text(encoding="utf-8"))


def install_plugin(profile: Path) -> dict:
    assert_isolated(profile)
    dest = plugin_dir(profile)
    generated = generate_plugin_tree(dest)
    settings_path(profile).parent.mkdir(parents=True, exist_ok=True)
    settings_path(profile).write_text(
        json.dumps(
            {
                "enabledPlugins": {PLUGIN_NAME: True},
                "claim": "installer-success-is-not-the-loaded-skill-report",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report = load_client_skills(dest, replace=None)
    write_inventory(profile, report)
    fs_files = filesystem_skill_files(dest)
    return {
        "plugin_dir": str(dest),
        "generated": generated,
        "client": report,
        "filesystem_count": len(fs_files),
        "filesystem_files": fs_files,
        "settings": str(settings_path(profile)),
        "inventory": str(inventory_path(profile)),
        "isolated": True,
    }


def uninstall_plugin(profile: Path) -> None:
    dest = plugin_dir(profile)
    if dest.exists():
        shutil.rmtree(dest)
    sp = settings_path(profile)
    if sp.exists():
        sp.unlink()
    runtime = profile / ".res0019-runtime"
    if runtime.exists():
        shutil.rmtree(runtime)
