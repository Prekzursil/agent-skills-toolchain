#!/usr/bin/env python3
"""Deploy-completeness gate for ``agent-self/bootstrap.ps1`` (D-wu-66).

``bootstrap.ps1`` is the one-shot "deploy this bundle onto a fresh machine"
script.  It ships ``agent-self/config/settings.json`` verbatim -- and that file
registers hook commands by ABSOLUTE deployed path
(``.../.claude/hooks/<pkg>/<script>``).  A registration whose script the script
never copies does not fail loudly: Claude Code just runs a command that is not
there, and the hook silently never fires.

MEASURED at 27fb388, before this gate existed: ``config/settings.json``
referenced 21 hook scripts and ``config/hooks/`` contained **4** of them.  The
other 17 -- including ``_dispatch/dispatch.py`` (the whole consolidated hook
set), ``per-edit-check``, ``no-force-push``, ``file-scope`` and
``selection-events`` -- existed only in the repo-root ``hooks/`` tree, which
bootstrap did not deploy.  Two cross-package imports had the same shape:
``config/hooks/inquisitiveness/prompt-guard.py`` inserts a sibling
``calibrated-silence`` directory that ``config/hooks/`` does not contain, and
its fail-open shim converts the resulting ImportError to ALLOW, so the
anti-nag calibration was permanently inert on a bootstrapped machine rather
than merely degraded (``prompt-guard.py`` ``_cs_allow``).  Same for
``event-ledger/ledger.py`` -> ``_shared``.

WHAT THIS GATE CAN AND CANNOT SAY: it checks the STATIC invariant -- every
deployed-path reference resolves inside a tree ``bootstrap.ps1`` copies into
``~/.claude``.  It does NOT execute PowerShell (CI is Linux), so it proves the
inputs are complete, not that a real run succeeded.  The copy lines themselves
are asserted as literal substrings so deleting one turns this red.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BOOTSTRAP = REPO / "agent-self" / "bootstrap.ps1"
SETTINGS = REPO / "agent-self" / "config" / "settings.json"

# Deploy map: destination subpath under ~/.claude  ->  (repo source tree, the
# literal ``Copy-Item`` line in bootstrap.ps1 that performs it).  Resolution
# below CONSULTS THE SCRIPT: an entry whose copy line is gone stops counting as
# deployed, so deleting the line turns the substantive assertions red too -- not
# just the self-check.  Verified in both states: reverting the hooks copy line
# reproduces the original 17-script miss.
DEPLOY_MAP: dict[str, tuple[str, str]] = {
    # config/*  -> ~/.claude
    "": (
        "agent-self/config",
        "Copy-Item (Join-Path $Self 'config\\*') $ClaudeHome -Recurse -Force",
    ),
    # hooks/*   -> ~/.claude/hooks
    "hooks/": (
        "hooks",
        "Copy-Item (Join-Path $RepoHooks '*') (Join-Path $ClaudeHome 'hooks') "
        "-Recurse -Force",
    ),
}
COPY_LINES: tuple[str, ...] = tuple(line for _, line in DEPLOY_MAP.values())

_REFERENCE = re.compile(r"\.claude/hooks/([A-Za-z0-9_./-]+\.(?:py|ps1|sh|js))")
# ``sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "<pkg>"))``
_SIBLING_IMPORT = re.compile(r'parent\.parent\s*/\s*"([^"]+)"')


def _deployed(relative_to_claude_home: str) -> bool:
    """True when some tree bootstrap.ps1 ACTUALLY copies provides this path."""
    script = BOOTSTRAP.read_text(encoding="utf-8")
    for destination, (source, copy_line) in DEPLOY_MAP.items():
        if copy_line not in script:
            continue  # the script does not perform this copy any more
        if relative_to_claude_home.startswith(destination):
            tail = relative_to_claude_home[len(destination) :]
            if (REPO / source / tail).exists():
                return True
    return False


def _settings_hook_references() -> dict[str, str]:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for event, matchers in settings.get("hooks", {}).items():
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                command = hook.get("command", "").replace(chr(92), "/")
                for rel in _REFERENCE.findall(command):
                    found.setdefault(rel, event)
    return found


@pytest.mark.parametrize("line", COPY_LINES)
def test_bootstrap_still_performs_the_copy_this_gate_assumes(line: str):
    """DEPLOY_MAP is a claim about bootstrap.ps1; keep it falsifiable."""
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert line in text, (
        f"bootstrap.ps1 no longer contains {line!r}; DEPLOY_MAP below is now "
        "fiction and every assertion in this file is measuring nothing"
    )


def test_detector_finds_the_known_present_references():
    """Control: a zero-miss verdict is worthless if the scan finds nothing."""
    references = _settings_hook_references()
    # 2026-10-17 blocking-mode consolidation removed six standalone PreToolUse
    # guard references from the mirror (now exec checks behind _dispatch), so
    # the distinct-reference floor tracks the shrunk registration surface.
    assert len(references) >= 14, (
        f"only {len(references)} hook references parsed out of settings.json - "
        "the regex is broken, not the configuration"
    )


def test_every_registered_hook_script_is_deployed():
    missing = sorted(
        f"{rel}  (registered for {event})"
        for rel, event in _settings_hook_references().items()
        if not _deployed(f"hooks/{rel}")
    )
    assert not missing, (
        "agent-self/config/settings.json registers hook scripts that "
        "bootstrap.ps1 never copies into ~/.claude - each is a silently dead "
        "hook on a freshly bootstrapped machine:\n  " + "\n  ".join(missing)
    )


def test_every_cross_package_sibling_import_is_deployed():
    """A hook that adds a sibling package to sys.path needs that sibling shipped."""
    config_hooks = REPO / "agent-self" / "config" / "hooks"
    missing: list[str] = []
    for module in sorted(config_hooks.rglob("*.py")):
        source = module.read_text(encoding="utf-8", errors="replace")
        for package in _SIBLING_IMPORT.findall(source):
            if not _deployed(f"hooks/{package}"):
                missing.append(
                    f"{module.relative_to(REPO).as_posix()} -> hooks/{package}"
                )
    assert not missing, (
        "hooks import a sibling package that bootstrap.ps1 does not deploy; the "
        "fail-open shims turn that into a silent no-op, not an error:\n  "
        + "\n  ".join(missing)
    )
