"""Executable regressions for four governance defects in the rules/commands surface.

These are prose-and-frontmatter defects, so nothing in the Python test tree covered
them.  They live here because ``skill-dual-write.yml`` runs ``pytest ci/tests`` as a
whole directory on every pull request -- there is no repo-wide pytest autodiscovery
in this repo, so a suite placed anywhere unnamed would simply never run.

Covered:

A005  the "full feature development process" was path-scoped away from Dart and
      C++ headers (and, by the same deterministic omission, from Perl entirely).
A020  rules/common/code-review.md graded HIGH as WARN while commands/code-review.md
      ordered a BLOCK on the same finding -- identical review state, opposite gate.
A139  commands/metaswarm-setup.md detected CLIs with Bash ``which``, which the
      repo's own Windows contract records as unable to see a ``.cmd`` shim.
A111  agents/chief-of-staff.md advertised a PostToolUse hook that blocks completion;
      no such check exists in either dispatcher graph.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# The two projections of the same governance surface.  agent-self/config/ is a
# committed snapshot of the live ~/.claude, so a fix applied to only one of them
# ships half-deployed.
TREES = ("", "agent-self/config/")

_GLOB = re.compile(r'-\s*"([^"]+)"')
_EXT_GLOB = re.compile(r"^\*\*/\*\.([A-Za-z0-9]+)$")

# Extensions a language dir declares that are NOT implementation source: project
# files and a test-only suffix.  Everything else a rules/<lang>/ dir claims is a
# surface a feature can be implemented in, and must therefore load the workflow.
NON_SOURCE_EXT = frozenset({"csproj", "sln", "t"})


def _frontmatter_globs(md: Path) -> set[str]:
    text = md.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return set(_GLOB.findall(m.group(1))) if m else set()


def _language_source_exts(tree: str) -> dict[str, set[str]]:
    """Map rules/<lang> -> the implementation extensions it declares."""
    root = REPO_ROOT / tree / "rules"
    out: dict[str, set[str]] = {}
    for d in sorted(p for p in root.iterdir() if p.is_dir() and p.name != "common"):
        exts: set[str] = set()
        for md in sorted(d.glob("*.md")):
            for g in _frontmatter_globs(md):
                m = _EXT_GLOB.match(g)
                if m and m.group(1) not in NON_SOURCE_EXT:
                    exts.add(m.group(1))
        out[d.name] = exts
    return out


# ── A005 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("tree", TREES)
def test_development_workflow_covers_every_installed_language(tree: str):
    """A supported language must not skip research/plan/TDD/review by filename.

    rules/README.md declares common rules universal and language rules an
    extension of them, but `paths:` frontmatter is what actually decides whether a
    rule loads.  A language dir that ships a rule for `.dart` while the common
    development workflow has no `.dart` glob means a Dart feature loads the Dart
    testing rule and NOT the pipeline it is supposed to extend.
    """
    wf = REPO_ROOT / tree / "rules" / "common" / "development-workflow.md"
    covered = {
        m.group(1)
        for g in _frontmatter_globs(wf)
        if (m := _EXT_GLOB.match(g)) is not None
    }
    missing: dict[str, set[str]] = {}
    for lang, exts in _language_source_exts(tree).items():
        gap = exts - covered
        if gap:
            missing[lang] = gap
    assert not missing, (
        f"{tree}rules/common/development-workflow.md paths[] omits implementation "
        f"extensions declared by the installed language matrix: {missing}"
    )


@pytest.mark.parametrize("tree", TREES)
@pytest.mark.parametrize("ext", ["dart", "hpp", "cc", "pl"])
def test_named_a005_extensions_load_the_workflow(tree: str, ext: str):
    """Pin the exact extensions the A005 probe counted at 0."""
    wf = REPO_ROOT / tree / "rules" / "common" / "development-workflow.md"
    assert f"**/*.{ext}" in _frontmatter_globs(wf)


# ── A020 ─────────────────────────────────────────────────────────────────────

# The command must not restate the gate; matches "Block ... HIGH" on one line.
_BLOCK_ON_HIGH = re.compile(r"\bBlock\b[^\n]*\bHIGH\b", re.IGNORECASE)


@pytest.mark.parametrize("tree", TREES)
def test_code_review_command_does_not_contradict_the_rule(tree: str):
    """One severity, one outcome.

    The rule grades HIGH as WARN / "merge with caution"; the command used to order
    "Block commit if CRITICAL or HIGH issues found".  A function over 50 lines is
    HIGH by the command's own taxonomy, so the same review state got opposite
    governance answers depending on which document was consulted.
    """
    rule = (REPO_ROOT / tree / "rules" / "common" / "code-review.md").read_text(
        encoding="utf-8", errors="replace"
    )
    cmd = (REPO_ROOT / tree / "commands" / "code-review.md").read_text(
        encoding="utf-8", errors="replace"
    )

    # The rule side is unchanged and still the source of truth.
    assert re.search(r"\|\s*HIGH\s*\|[^|]*\|[^|]*WARN", rule), (
        "the rule's HIGH row no longer grades WARN -- if that was intentional, "
        "the command's gate must move with it"
    )
    assert "**Block**: CRITICAL issues found" in rule

    offenders = [ln for ln in cmd.splitlines() if _BLOCK_ON_HIGH.search(ln)]
    assert not offenders, (
        f"{tree}commands/code-review.md orders a block on HIGH, which the rule "
        f"grades WARN: {offenders}"
    )
    assert "code-review.md" in cmd, "the command must defer to the rule's table"


# ── A139 ─────────────────────────────────────────────────────────────────────

# An INSTRUCTION to probe a CLI with `which`. Written to match the imperative form
# only, so a sentence warning *against* `which` is not a false positive.
_WHICH_INSTRUCTION = re.compile(r"(?:run|via|check via|check with)\s+`?which\s+\w")


@pytest.mark.parametrize("tree", TREES)
def test_metaswarm_setup_uses_the_windows_safe_cli_probe(tree: str):
    """rules/common/windows-shell.md §8 is explicit: `which` misses `.cmd` shims.

    On the declared Windows host an npm-installed `codex.cmd` is invisible to Bash
    `which`, so the setup command reported an installed tool as absent, offered a
    redundant global npm install, and could persist `enabled: false`.
    """
    cmd_path = REPO_ROOT / tree / "commands" / "metaswarm-setup.md"
    cmd = cmd_path.read_text(encoding="utf-8", errors="replace")

    offenders = [ln.strip() for ln in cmd.splitlines() if _WHICH_INSTRUCTION.search(ln)]
    assert not offenders, (
        f"{tree}commands/metaswarm-setup.md still instructs a bare `which` probe: "
        f"{offenders}"
    )
    assert "Get-Command" in cmd, (
        "the Windows branch of the CLI-presence probe is missing"
    )


def test_windows_shell_rule_still_mandates_get_command():
    """Detector control: the contract A139 is measured against must still say so.

    If this rule is ever relaxed, the assertion above is measuring nothing.
    """
    rule = (REPO_ROOT / "rules" / "common" / "windows-shell.md").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "Get-Command" in rule and "`.cmd` shims" in rule


# ── A111 ─────────────────────────────────────────────────────────────────────

_CLAIMS_ENFORCEMENT = re.compile(
    r"enforced by a `PostToolUse` hook|hook that blocks completion", re.IGNORECASE
)
_COMMS_MATCHER = re.compile(
    r"gmail|slack|conversations_add_message|send", re.IGNORECASE
)


def _posttooluse_checks() -> list[dict]:
    manifest = json.loads(
        (REPO_ROOT / "hooks" / "_dispatch" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    return manifest["events"]["PostToolUse"]["checks"]


def test_chief_of_staff_does_not_advertise_a_hook_that_does_not_exist():
    """An advisory checklist must not be described as deterministic enforcement.

    Stated as an implication rather than a bare string ban, so the assertion stays
    correct if the hook is actually BUILT later: the doc may claim enforcement
    exactly when a PostToolUse check matching the communications tools exists.
    """
    doc = (REPO_ROOT / "agents" / "chief-of-staff.md").read_text(
        encoding="utf-8", errors="replace"
    )
    claims = bool(_CLAIMS_ENFORCEMENT.search(doc))
    has_comms_check = any(
        _COMMS_MATCHER.search(c.get("matcher", "") or "")
        or _COMMS_MATCHER.search(c.get("name", "") or "")
        for c in _posttooluse_checks()
    )
    assert not claims or has_comms_check, (
        "agents/chief-of-staff.md claims a PostToolUse hook enforces the "
        "post-send checklist, but no PostToolUse check in "
        "hooks/_dispatch/manifest.json matches gmail/slack/send"
    )


def test_dispatcher_posttooluse_inventory_is_the_one_a111_measured():
    """Detector control for the test above.

    Pins the exact three checks A111 found, so a future PostToolUse addition
    forces a human to re-read the claim rather than silently flipping the
    implication test to vacuously true.
    """
    assert [c["name"] for c in _posttooluse_checks()] == [
        "memory-spool/flush_check",
        "tool-result-sentinel",
        "stub-ledger/record",
    ]
