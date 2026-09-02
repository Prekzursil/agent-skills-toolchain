"""Contracted plugin surface for the REL-0004 canary drill.

B07's live packaged artifact is not present in this worktree. The drill
installs this file-backed package from a local mirror. The contracted hook
set is the plugin's own declared events — every one must produce a runtime
side effect. A directory listing is not an acceptance signal.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE_PACKAGE = HERE / "fixtures" / "package"

PLUGIN_ID = "rel-0004-canary-harness"
PLUGIN_VERSION = "1.0.0"
CONTRACTED_EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "Stop")
MISREGISTER_EVENT = "PreToolUse"
EXPECTED_RELATIVE_FILES = ("plugin.json", "hooks.json", "hooks/effect.py")
INSTALL_SUBDIR = Path(".claude") / "plugins" / PLUGIN_ID
EFFECTS_DIRNAME = "canary-effects"
