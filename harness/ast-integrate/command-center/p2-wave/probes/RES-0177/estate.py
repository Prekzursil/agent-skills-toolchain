#!/usr/bin/env python3
"""Detector-control fixture estate for RES-0177.

Known-present: hookify (plugin.json + listing).
Fabricated name: xyzzy-not-installed-res0177 (empty directory, no manifest).
Noise directory: looks-like-plugin (README only, no plugin.json).

The six catalog-named plugins that have a published plugin.json are
planted from cache/. ``codex`` has no marketplace plugin.json identity
and is not planted.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
ESTATE = HERE / "fixtures" / "estate"
HOME = ESTATE / "home"
PLUGINS = HOME / ".claude" / "plugins" / "marketplaces" / "lab" / "plugins"

from enumerate import FABRICATED_NAME, KNOWN_PRESENT, NOISE_DIR_NAME  # noqa: E402

CATALOG_NAMED = (
    "metaswarm",
    "superpowers",
    "hookify",
    "claude-reflect",
    "ralph-loop",
    "remember",
)


def _read(name: str) -> str:
    return (CACHE / name).read_text(encoding="utf-8")


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not body.endswith("\n"):
        body += "\n"
    path.write_text(body, encoding="utf-8")


def plant_plugin(name: str, plugin_json: str, extra: dict[str, str] | None = None) -> None:
    root = PLUGINS / name
    _write(root / ".claude-plugin" / "plugin.json", plugin_json)
    for rel, body in (extra or {}).items():
        _write(root / rel, body)


def write_estate() -> dict:
    if ESTATE.exists():
        for path in sorted(ESTATE.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass

    plant_plugin("hookify", _read("hookify.plugin.json"), {"hooks/hooks.json": _read("hookify.hooks.json")})
    plant_plugin(
        "ralph-loop",
        _read("ralph-loop.plugin.json"),
        {"hooks/hooks.json": _read("ralph-loop.hooks.json")},
    )
    plant_plugin("superpowers", _read("superpowers.plugin.json"), {"skills/using-superpowers/SKILL.md": "# using-superpowers\n"})
    plant_plugin(
        "remember",
        _read("remember.plugin.json"),
        {"hooks/hooks.json": _read("remember.hooks.json")},
    )
    plant_plugin(
        "claude-reflect",
        _read("claude-reflect.plugin.json"),
        {"hooks/hooks.json": _read("claude-reflect.hooks.json")},
    )
    plant_plugin("metaswarm", _read("metaswarm.plugin.json"), {"commands/phase.md": "# /metaswarm-phase\n"})

    _write((PLUGINS / NOISE_DIR_NAME / "README.md"), "# not a plugin\nDirectory noise: no plugin.json.\n")
    (PLUGINS / FABRICATED_NAME).mkdir(parents=True, exist_ok=True)
    (PLUGINS / FABRICATED_NAME / "placeholder.txt").write_text(
        "fabricated name directory; no plugin.json\n", encoding="utf-8"
    )

    marketplace = {
        "name": "lab",
        "owner": {"name": "res-0177-fixture"},
        "plugins": [{"name": n, "source": f"./plugins/{n}"} for n in CATALOG_NAMED],
    }
    _write(
        HOME / ".claude" / "plugins" / "marketplaces" / "lab" / ".claude-plugin" / "marketplace.json",
        json.dumps(marketplace, indent=2),
    )

    enabled = {f"{n}@lab": True for n in CATALOG_NAMED}
    _write(HOME / ".claude" / "settings.json", json.dumps({"enabledPlugins": enabled}, indent=2))

    listing = {
        "plugins": [
            {
                "id": f"{n}@lab",
                "name": n,
                "marketplace": "lab",
                "enabled": True,
                "status": "enabled",
            }
            for n in CATALOG_NAMED
        ]
    }
    _write(ESTATE / "claude-plugin-list.json", json.dumps(listing, indent=2))
    lines = ["Installed plugins:", ""]
    for n in CATALOG_NAMED:
        lines.append(f"{n}@lab")
        lines.append("  Status: enabled")
        lines.append("")
    _write(ESTATE / "claude-plugin-list.txt", "\n".join(lines))

    return {
        "estate": str(ESTATE),
        "plugins_root": str(PLUGINS),
        "known_present": KNOWN_PRESENT,
        "fabricated": FABRICATED_NAME,
        "noise_dir": NOISE_DIR_NAME,
        "catalog_named_planted": list(CATALOG_NAMED),
        "listing_json": str(ESTATE / "claude-plugin-list.json"),
        "listing_text": str(ESTATE / "claude-plugin-list.txt"),
    }


def load_estate() -> dict:
    if not (ESTATE / "claude-plugin-list.json").is_file():
        write_estate()
    return {
        "estate": ESTATE,
        "plugins_root": PLUGINS,
        "listing_json": ESTATE / "claude-plugin-list.json",
        "listing_text": ESTATE / "claude-plugin-list.txt",
        "known_present": KNOWN_PRESENT,
        "fabricated": FABRICATED_NAME,
        "noise_dir": NOISE_DIR_NAME,
        "catalog_named_planted": list(CATALOG_NAMED),
    }


if __name__ == "__main__":
    info = write_estate()
    print(json.dumps(info, indent=2, sort_keys=True))
    print("SUCCESS:RES-0177-estate")
