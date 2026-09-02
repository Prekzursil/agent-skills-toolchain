"""Known-broken, known-good, and mention-only events for both-states."""
from __future__ import annotations

from typing import Any

# Structured USE of Bash: verb is Bash, payload does not contain the word.
USE_BASH: dict[str, Any] = {
    "id": "use-bash",
    "tool": {"verb": "Bash"},
    "payload_text": "ls -la /tmp && echo done",
}

# MENTION of Bash in a Read payload. Use-versus-mention control.
MENTION_BASH: dict[str, Any] = {
    "id": "mention-bash",
    "tool": {"verb": "Read"},
    "payload_text": (
        "The forbidden tool verb Bash is discussed in this document; "
        "do not confuse mention with use."
    ),
}

# Known-good: Read, no Bash mention, no Bash verb.
GOOD_READ: dict[str, Any] = {
    "id": "good-read",
    "tool": {"verb": "Read"},
    "payload_text": "read README.md from the worktree",
}

MISSING_ARTIFACT_REQUIRE_DEFAULT: dict[str, Any] = {
    "id": "missing-artifact-require-unset",
    "artifact_present": False,
    "require_flag": None,
}

MISSING_ARTIFACT_REQUIRE_ON: dict[str, Any] = {
    "id": "missing-artifact-require-on",
    "artifact_present": False,
    "require_flag": True,
}

PRESENT_ARTIFACT_REQUIRE_ON: dict[str, Any] = {
    "id": "present-artifact-require-on",
    "artifact_present": True,
    "require_flag": True,
}

ABSENT_INPUT: dict[str, Any] = {
    "id": "absent-input",
    "input_present": False,
    "input": None,
    "is_bad": True,
}

PRESENT_BAD: dict[str, Any] = {
    "id": "present-bad",
    "input_present": True,
    "input": {"secret": "CANARY"},
    "is_bad": True,
}

PRESENT_GOOD: dict[str, Any] = {
    "id": "present-good",
    "input_present": True,
    "input": {"ok": True},
    "is_bad": False,
}

EXCEPT_ON_USE: dict[str, Any] = {
    "id": "except-on-use",
    "tool": {"verb": "Bash"},
    "payload_text": "ls -la /tmp && echo done",
    "raise_eval_error": True,
}
