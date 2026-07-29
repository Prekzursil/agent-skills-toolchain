"""A slash command must not prescribe reading a file the shipped settings deny.

``agent-self/config/settings.json`` is not an unrelated example: it is the
committed snapshot of the live ``~/.claude/settings.json`` (paired by
``scripts/build-codespace-mirror.py``) and is installed verbatim as the user
``settings.json`` by ``scripts/bootstrap-codespace.sh``.  Its
``permissions.deny`` list carries ``Read(./.env)`` and ``Read(**/.env)``, and a
deny rule outranks allow/ask and stays in force under
``defaultMode: "bypassPermissions"``.

``commands/pm2.md`` nonetheless documented ``.env`` as the highest-priority port
source after an explicit argument, with no fallback and no mention that the read
can be refused.  On a project whose ``.env`` sets ``PORT=4317`` while the config
file / framework default resolve to 3000, ``/pm2`` therefore either stalls on the
refused read or silently falls through and writes an ``ecosystem.config.cjs``
pinned to the wrong port.  The command is now deny-aware; these tests keep it
that way, and keep the ``agent-self`` mirror in step so the fix cannot ship to
only one of the two copies.

Detector note: a command "prescribes a project ``.env`` read" when ``.env``
appears in PROSE -- outside fenced code blocks, not as the JS ``process.env``
accessor, and not as a longer suffixed name.  That last exclusion is
load-bearing and was found by running the detector before trusting it: a naive
``\\.env\\b`` also fires on ``.env.example``, which ``Read(**/.env)`` does NOT
cover, so it flagged ``commands/update-docs.md:31`` -- a file that already does
the right thing by reading ``.env.example``.

Measured after that repair: ``commands/pm2.md:29`` (and its ``agent-self``
mirror) is the only prose line matching across all 71 command files.
``metaswarm-setup.md``'s ``.env`` lines sit inside ``.gitignore`` code fences,
``e2e.md`` / ``sessions.md`` only use ``process.env``, and ``update-docs.md``
only names the ``.env.example`` family.  The guard is therefore general over the
command surface rather than hardcoded to ``/pm2``.
"""

from __future__ import annotations

import json
import re
from fnmatch import fnmatch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS = REPO_ROOT / "agent-self" / "config" / "settings.json"
COMMAND_DIRS = (
    REPO_ROOT / "commands",
    REPO_ROOT / "agent-self" / "config" / "commands",
)
PM2 = REPO_ROOT / "commands" / "pm2.md"
PM2_MIRROR = REPO_ROOT / "agent-self" / "config" / "commands" / "pm2.md"

# A prose (non-fenced) ``.env`` that is neither the JS ``process.env`` accessor
# (excluded by the lookbehind) nor a longer, undenied name such as
# ``.env.example`` / ``.env.local`` (excluded by the lookahead).
PROSE_ENV = re.compile(r"(?<![\w.])\.env(?![\w.-])")
FENCE = re.compile(r"^\s*`{3,}")
READ_RULE = re.compile(r"^Read\((?P<glob>.+)\)$")

# The three elements deny-aware guidance must supply, all in the SAME section as
# the ``.env`` mention -- guidance buried at the bottom of the document does not
# reach the model at the point it decides how to resolve the port.
REQUIRED_CUES = {
    "names the permission refusal": re.compile(
        r"\bden(?:y|ied|ies)\b|\bblocked\b|\bpermission\b", re.IGNORECASE
    ),
    "offers a readable substitute": re.compile(r"\.env\.example", re.IGNORECASE),
    "falls back to asking the owner": re.compile(r"ask the user", re.IGNORECASE),
}


def deny_globs() -> list[str]:
    """The glob payload of every ``Read(...)`` entry in ``permissions.deny``."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    globs: list[str] = []
    for rule in settings["permissions"]["deny"]:
        match = READ_RULE.match(rule)
        if match:
            globs.append(match.group("glob"))
    return globs


def read_is_denied(path: str) -> bool:
    """Does any deny glob cover ``path``?  Matched both bare and ``./``-prefixed."""
    candidates = {path, f"./{path}"} if not path.startswith("./") else {path, path[2:]}
    return any(
        fnmatch(candidate, glob) for glob in deny_globs() for candidate in candidates
    )


def sections(text: str) -> list[str]:
    """Split a command document into ``##``-level sections, code fences intact."""
    chunks: list[list[str]] = [[]]
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and line.startswith("## "):
            chunks.append([])
        chunks[-1].append(line)
    return ["\n".join(chunk) for chunk in chunks]


def prose_env_sections(text: str) -> list[str]:
    """Sections whose prose (non-fenced) body names a project ``.env``."""
    found = []
    for section in sections(text):
        in_fence = False
        for line in section.splitlines():
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if not in_fence and PROSE_ENV.search(line):
                found.append(section)
                break
    return found


def command_files() -> list[Path]:
    return sorted(
        path
        for directory in COMMAND_DIRS
        if directory.is_dir()
        for path in directory.glob("*.md")
    )


def test_settings_snapshot_denies_reading_a_project_env_file() -> None:
    """The premise. If this ever stops holding, revisit the guidance below."""
    assert SETTINGS.is_file(), f"missing {SETTINGS}"
    assert read_is_denied(".env"), f"no deny glob covers .env in {deny_globs()}"
    assert read_is_denied("packages/web/.env"), "nested .env is not covered"
    # The substitute the guidance points at must NOT be swept up by the same denies.
    assert not read_is_denied(".env.example"), ".env.example is itself denied"


def test_pm2_still_names_env_as_a_port_source() -> None:
    """Anchors the finding: remove the claim and the guard below is moot."""
    assert PM2.is_file(), f"missing {PM2}"
    assert prose_env_sections(PM2.read_text(encoding="utf-8")), (
        "commands/pm2.md no longer names .env in prose -- retire or rescope this suite"
    )


def test_the_env_detector_ignores_process_env_fenced_blocks_and_example_files() -> None:
    """Detector control: a probe that fires on everything measures nothing.

    The ``.env.example`` case is a real false positive this detector produced
    against ``commands/update-docs.md:31`` before the lookahead was added.
    """
    assert not prose_env_sections("## S\n\nUse `process.env.PORT` at runtime.\n")
    assert not prose_env_sections("## S\n\n```gitignore\n.env\n.env.local\n```\n")
    assert not prose_env_sections("## S\n\nRead `.env.example` for the keys.\n")
    assert not prose_env_sections("## S\n\nRead `.env.template`/`.env.sample`.\n")
    assert prose_env_sections("## S\n\nRead .env for the port.\n")
    assert prose_env_sections("## S\n\nRead `.env` for the port.\n")


def test_commands_that_prescribe_an_env_read_are_deny_aware() -> None:
    """The guard. A denied source needs a substitute and an escalation path."""
    missing: list[str] = []
    for path in command_files():
        for section in prose_env_sections(path.read_text(encoding="utf-8")):
            for label, cue in REQUIRED_CUES.items():
                if not cue.search(section):
                    missing.append(f"{path.relative_to(REPO_ROOT)}: {label}")
    assert not missing, (
        "a command names a project .env that agent-self/config/settings.json denies, "
        "without deny-aware guidance beside it: " + "; ".join(missing)
    )


def test_pm2_command_and_its_agent_self_mirror_stay_identical() -> None:
    """Both copies ship. Fixing one and forgetting the other leaves it exposed.

    Scoped to pm2.md on purpose: ``commands/`` and
    ``agent-self/config/commands/`` are NOT a strict mirror (71 vs 66 files, and
    agent-monitor / harness-audit / mcp-gui differ by design), so a blanket
    parity assertion would be wrong.  These two are byte-identical today and are
    the same document.
    """
    assert PM2_MIRROR.is_file(), f"missing {PM2_MIRROR}"
    assert PM2.read_bytes() == PM2_MIRROR.read_bytes(), (
        "commands/pm2.md and agent-self/config/commands/pm2.md have diverged"
    )
