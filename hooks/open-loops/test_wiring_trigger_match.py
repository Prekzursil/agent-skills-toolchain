#!/usr/bin/env python3
"""Reachability gate for open-loops/trigger_match.py (D-a088).

``trigger_match.py`` is the ACTIVE half of prospective memory: ``add.py`` stores
a user-authored contextual trigger and ``trigger_match.py`` fires it on the next
matching human turn.  ``resurface.py`` (the SessionStart half) is wired through
``hooks/_dispatch/manifest.json``; ``trigger_match.py`` was not wired anywhere,
so every contextual trigger a user stored was unreachable -- ``add.py`` accepted
it, the store recorded it, and nothing ever read it back.

WHY A STANDALONE settings.json ENTRY AND NOT A MANIFEST CHECK: ``dispatch.py``
accepts exactly ``sessionstart | stop | posttooluse | pretooluse`` (its module
docstring, and ``manifest.json`` declares no ``UserPromptSubmit`` event), so a
manifest entry would be inert.  ``trigger_match.py``'s own wire spec asks for a
standalone UserPromptSubmit command, which is also how the sibling
``selection-events/emitter.py`` is registered.

SCOPE: this asserts the TRACKED deploy surface ``agent-self/config/settings.json``.
The live ``~/.claude/settings.json`` is machine-local and untracked, so CI cannot
see it -- ``hooks/_dispatch/test_wiring.py`` skips every live-settings assertion
for that reason.  This suite therefore proves the shipped configuration is
correct, NOT that any particular machine has deployed it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

HOOK_DIR = Path(__file__).resolve().parent
REPO = HOOK_DIR.parents[1]
SETTINGS = REPO / "agent-self" / "config" / "settings.json"
MANIFEST = REPO / "hooks" / "_dispatch" / "manifest.json"

# The wire spec trigger_match.py documents for itself.
TRIGGER_MATCH_SCRIPT = "hooks/open-loops/trigger_match.py"
# Already-registered sibling on the same event -- the DETECTOR CONTROL.  If the
# scan below cannot find this, a zero hit for trigger_match means nothing.
CONTROL_SCRIPT = "hooks/selection-events/emitter.py"


def _user_prompt_submit_commands() -> list[str]:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return [
        hook.get("command", "")
        for matcher in settings.get("hooks", {}).get("UserPromptSubmit", [])
        for hook in matcher.get("hooks", [])
    ]


def _hits(script: str) -> list[str]:
    needle = script.replace("hooks/", "/hooks/")
    return [c for c in _user_prompt_submit_commands() if needle in c.replace("\\", "/")]


def test_detector_control_sees_the_already_registered_sibling():
    """A zero hit is only evidence if the scan can find a KNOWN-present entry."""
    assert _hits(CONTROL_SCRIPT), (
        "detector failure: the UserPromptSubmit scan cannot even find "
        f"{CONTROL_SCRIPT}, so it cannot testify about anything else"
    )


def test_trigger_match_is_registered_for_user_prompt_submit():
    hits = _hits(TRIGGER_MATCH_SCRIPT)
    assert len(hits) == 1, (
        "open-loops/trigger_match.py must have exactly one UserPromptSubmit "
        f"registration in {SETTINGS.name}; found {len(hits)}: {hits}. Without it "
        "every stored contextual trigger is write-only -- add.py records it and "
        "nothing ever fires it."
    )


def test_trigger_match_registration_is_inject_only_and_bounded():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    entries = [
        hook
        for matcher in settings["hooks"]["UserPromptSubmit"]
        for hook in matcher.get("hooks", [])
        if "/hooks/open-loops/trigger_match.py"
        in hook.get("command", "").replace("\\", "/")
    ]
    (entry,) = entries
    assert entry.get("type") == "command"
    timeout = entry.get("timeout")
    assert isinstance(timeout, int) and 0 < timeout <= 10, (
        "a UserPromptSubmit hook runs on the human's critical path; "
        f"timeout must be a small positive int, got {timeout!r}"
    )


def test_trigger_match_is_not_folded_into_the_inject_only_dispatcher():
    """A manifest entry would be INERT: dispatch.py has no UserPromptSubmit event."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert "UserPromptSubmit" not in manifest["events"], (
        "manifest.json gained a UserPromptSubmit event; dispatch.py only accepts "
        "sessionstart|stop|posttooluse|pretooluse, so those checks would never run"
    )
    folded = [
        check["name"]
        for event in manifest["events"].values()
        for check in event.get("checks", [])
        if "trigger_match" in check.get("script", "")
    ]
    assert not folded, f"trigger_match folded into an unreachable event: {folded}"


@pytest.mark.parametrize("path", [SETTINGS, MANIFEST])
def test_registration_documents_exist(path: Path):
    assert path.is_file(), f"missing registration document {path}"
