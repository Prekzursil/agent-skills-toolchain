#!/usr/bin/env python3
"""Fixture estate that reproduces the WFA-0018 right-key-wrong-file trap.

Known-enabled: harness@lab (commands + workflows)
Known-disabled: agentbridge@lab (commands present; disabled in settings.json)
Enabled workflow plugin: metaswarm@lab
Marketplace-only, no commands: docs-only@lab

~/.claude.json (root and per-project) INVERTS harness/agentbridge and adds
root-ghost@lab. Runtime `claude plugin list` capture honors settings.json.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ESTATE = HERE / "fixtures" / "estate"
HOME = ESTATE / "home"
KNOWN_ENABLED = "harness@lab"
KNOWN_DISABLED = "agentbridge@lab"
PROJECT = "/opt/p2/ast-integrate"

SETTINGS = {
    "enabledPlugins": {
        "harness@lab": True,
        "agentbridge@lab": False,
        "metaswarm@lab": True,
    }
}

CLAUDE_JSON = {
    "enabledPlugins": {
        "harness@lab": False,
        "agentbridge@lab": True,
        "root-ghost@lab": True,
    },
    "projects": {
        PROJECT: {
            "enabledPlugins": {
                "harness@lab": False,
                "agentbridge@lab": True,
            }
        }
    },
}

PLUGIN_LIST_JSON = {
    "plugins": [
        {
            "id": "harness@lab",
            "name": "harness",
            "marketplace": "lab",
            "enabled": True,
            "status": "enabled",
        },
        {
            "id": "agentbridge@lab",
            "name": "agentbridge",
            "marketplace": "lab",
            "enabled": False,
            "status": "disabled",
        },
        {
            "id": "metaswarm@lab",
            "name": "metaswarm",
            "marketplace": "lab",
            "enabled": True,
            "status": "enabled",
        },
    ]
}

PLUGIN_LIST_TEXT = """Installed plugins:

harness@lab
  Status: enabled

agentbridge@lab
  Status: disabled

metaswarm@lab
  Status: enabled
"""

MARKETPLACE = {
    "name": "lab",
    "owner": {"name": "wfa-0018-fixture"},
    "plugins": [
        {"name": "harness", "source": "./plugins/harness"},
        {"name": "agentbridge", "source": "./plugins/agentbridge"},
        {"name": "metaswarm", "source": "./plugins/metaswarm"},
        {"name": "docs-only", "source": "./plugins/docs-only"},
    ],
}

PLUGINS = {
    "harness": {
        "plugin": {
            "name": "harness",
            "version": "1.0.0",
            "description": "Fixture known-enabled workflow plugin",
            "commands": ["./commands/run.md"],
        },
        "files": {
            "commands/run.md": "# /harness-run\n\nPlan, execute, review.\n",
            "workflows/pack.json": json.dumps(
                {"name": "harness-pack", "stages": ["plan", "execute", "review"]},
                indent=2,
            )
            + "\n",
        },
    },
    "agentbridge": {
        "plugin": {
            "name": "agentbridge",
            "version": "0.1.0",
            "description": "Fixture known-disabled plugin (AUD-0016 control)",
            "commands": ["./commands/bridge.md"],
        },
        "files": {
            "commands/bridge.md": "# /bridge\n\nDisabled on this estate.\n",
        },
    },
    "metaswarm": {
        "plugin": {
            "name": "metaswarm",
            "version": "1.0.0",
            "description": "Fixture enabled plugin with commands and a skill",
            "commands": ["./commands/phase.md"],
        },
        "files": {
            "commands/phase.md": "# /metaswarm-phase\n\nNine-phase pipeline.\n",
            "skills/setup/SKILL.md": "# metaswarm-setup\n\nOrdered setup procedure.\n",
        },
    },
    "docs-only": {
        "plugin": {
            "name": "docs-only",
            "version": "1.0.0",
            "description": "Marketplace entry with no commands or workflows",
        },
        "files": {
            "README.md": "# docs-only\n\nDocumentation only. Not a workflow contributor.\n",
        },
    },
}


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")


def dump(path: Path, doc: object) -> None:
    _write(path, json.dumps(doc, indent=2, sort_keys=True) + "\n")


def ensure_estate() -> Path:
    dump(HOME / ".claude" / "settings.json", SETTINGS)
    dump(HOME / ".claude.json", CLAUDE_JSON)
    dump(ESTATE / "claude-plugin-list.json", PLUGIN_LIST_JSON)
    _write(ESTATE / "claude-plugin-list.txt", PLUGIN_LIST_TEXT)
    market = HOME / ".claude" / "plugins" / "marketplaces" / "lab"
    dump(market / ".claude-plugin" / "marketplace.json", MARKETPLACE)
    for name, spec in PLUGINS.items():
        root = market / "plugins" / name
        dump(root / ".claude-plugin" / "plugin.json", spec["plugin"])
        for rel, body in spec["files"].items():
            _write(root / rel, body)
    return ESTATE


def load_estate() -> dict:
    ensure_estate()
    settings = json.loads(
        (HOME / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    claude = json.loads((HOME / ".claude.json").read_text(encoding="utf-8"))
    captured = json.loads(
        (ESTATE / "claude-plugin-list.json").read_text(encoding="utf-8")
    )
    text = (ESTATE / "claude-plugin-list.txt").read_text(encoding="utf-8")
    return {
        "home": HOME,
        "settings_doc": settings,
        "claude_doc": claude,
        "plugin_list_json": captured,
        "plugin_list_text": text,
        "known_enabled": KNOWN_ENABLED,
        "known_disabled": KNOWN_DISABLED,
        "project": PROJECT,
    }
