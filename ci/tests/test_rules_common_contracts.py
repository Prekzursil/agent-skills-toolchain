"""Executable contracts for the `rules/common/*.md` documents.

These rules are not prose decoration: each one is *mechanized* somewhere in the
tree (a jq producer, a PowerShell sync tool, a hook generator, a claim gate), so
a rule that drifts away from the thing it governs silently mis-instructs every
agent that reads it. Nothing else in CI compares the two, which is how all eight
defects below shipped at once.

Each test pins ONE measured defect and, where possible, pins it as a
*consistency* property against the current implementation rather than as a
string match -- so hardening the implementation later cannot leave a stale
assertion asserting the old world.

Run (there is no repo-wide pytest autodiscovery; quality.yml names this file):

    pytest ci/tests/test_rules_common_contracts.py -q
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMON = REPO_ROOT / "rules" / "common"
BUNDLE_COMMON = REPO_ROOT / "agent-self" / "config" / "rules" / "common"

US = chr(0x1F)


def read(path: Path) -> str:
    """Universal-newline read: assertions must not depend on CRLF vs LF."""
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# D-wu-54 -- the prescribed jq record separator vanished from the producer.
# --------------------------------------------------------------------------

BASH_HUD = COMMON / "bash-hud-and-terminal-emit.md"


def test_bash_hud_rule_carries_no_literal_control_byte() -> None:
    """Section 8 of this very rule forbids the literal byte in the document."""
    assert BASH_HUD.read_bytes().count(b"\x1f") == 0


def _prescribed_separator() -> str:
    """Decode the separator the rule's section-2 fix actually prescribes.

    The rule writes it as a jq string literal, so decode it the way jq would
    rather than string-matching the escape -- that keeps this test honest if
    the spelling changes but the meaning does not.
    """
    fix = [ln for ln in read(BASH_HUD).splitlines() if "gsub(" in ln and "join(" in ln]
    assert len(fix) == 1, "expected exactly one section-2 jq producer line"
    m = re.search(r'join\("((?:[^"\\]|\\.)*)"\)', fix[0])
    assert m is not None, "section-2 fix no longer contains a jq join(...)"
    return json.loads('"%s"' % m.group(1))


def test_bash_hud_prescribes_the_us_separator() -> None:
    assert _prescribed_separator() == US


@pytest.mark.parametrize(
    ("left", "right"),
    [(["ab", "c"], ["a", "bc"]), (["", "x"], ["x", ""])],
)
def test_prescribed_separator_keeps_distinct_records_distinct(
    left: list[str], right: list[str]
) -> None:
    """The defect, stated behaviourally.

    With the empty separator the rule shipped, ["ab","c"] and ["a","bc"] both
    serialize to "abc" and the documented `IFS="$US" read -r` parse silently
    puts the concatenation in field 1. A record delimiter that aliases distinct
    records is not a delimiter.
    """
    sep = _prescribed_separator()
    assert sep.join(left) != sep.join(right)
    assert sep.join(left).split(sep) == left
    assert sep.join(right).split(sep) == right


def test_bash_hud_matches_the_shipped_statusline_producer() -> None:
    """The rule must prescribe what the working consumer actually uses."""
    statusline = read(REPO_ROOT / "agent-self" / "config" / "statusline-command.sh")
    seps = {
        json.loads('"%s"' % m)
        for m in re.findall(r'join\("((?:[^"\\]|\\.)*)"\)', statusline)
    }
    assert seps, "statusline producer no longer calls jq join()"
    assert seps == {_prescribed_separator()}


# --------------------------------------------------------------------------
# D-wu-41 -- the rule advertised a MUTATING sync as the way to inspect drift.
# --------------------------------------------------------------------------

VCS_HYGIENE = COMMON / "harness-vcs-hygiene.md"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync-from-live.ps1"


def _report_only_switch_is_honoured() -> bool:
    """True iff `-Report` alone selects a non-writing run in the real script."""
    for line in read(SYNC_SCRIPT).splitlines():
        if re.match(r"\s*\$writeAllowed\s*=", line):
            return "Report" in line
    raise AssertionError("sync-from-live.ps1 no longer assigns $writeAllowed")


def test_rule_does_not_advertise_bare_report_as_inspection() -> None:
    """Consistency property, so hardening the script cannot strand this test.

    While `$writeAllowed` ignores `-Report`, the rule must not present bare
    `-Report json` as a way to *see* drift, and must say the safe form.
    """
    if _report_only_switch_is_honoured():
        pytest.skip("sync-from-live.ps1 now honours -Report as read-only")
    text = read(VCS_HYGIENE)
    assert "-Drift -Report json" in text
    assert not re.search(r"`-Report json`\s*to see drift", text)
    assert "Bare `-Report json` WRITES" in text


def test_rule_warns_the_pre_write_guard_is_staged_only() -> None:
    """`git diff --cached` cannot see the unstaged edit it would overwrite."""
    assert "git diff --cached --name-only" in read(SYNC_SCRIPT)
    assert "STAGED paths only" in read(VCS_HYGIENE)


# --------------------------------------------------------------------------
# D-wu-73 / D-a012 -- the hooks rule's event surface and tool-family names.
# --------------------------------------------------------------------------

HOOKS_RULE = COMMON / "hooks.md"


def test_hooks_rule_names_every_generated_event() -> None:
    """The rule listed 3 of the generator's 16 events."""
    registration = read(REPO_ROOT / "agent-self" / "harness" / "registration.py")
    block = registration.split("EVENTS = (", 1)[1].split(")", 1)[0]
    events = re.findall(r'"(\w+)"', block)
    assert len(events) >= 16, "EVENTS tuple unexpectedly small"
    text = read(HOOKS_RULE)
    missing = [e for e in events if e not in text]
    assert not missing, "hooks rule omits generated events: %s" % missing


def test_hooks_rule_names_the_unwired_notification_event() -> None:
    """notify-idle requires `Notification`; the generator never emits it."""
    notify = read(REPO_ROOT / "hooks" / "notify-idle" / "notify.py")
    assert "Notification" in notify
    text = read(HOOKS_RULE)
    assert "Notification" in text
    assert "notify-idle" in text


@pytest.mark.parametrize("tool", ["TaskCreate", "TaskUpdate", "TaskList", "TaskGet"])
def test_hooks_rule_names_the_current_task_tools(tool: str) -> None:
    assert tool in read(HOOKS_RULE)


def test_hooks_rule_says_progress_bookkeeping_is_not_verification() -> None:
    """The honest-signal false negative, stated as guidance."""
    text = read(HOOKS_RULE)
    assert "Progress bookkeeping is NOT verification" in text
    assert "_NON_VERIFYING" in text


# --------------------------------------------------------------------------
# D-wu-18 -- fail-closed covered an empty WALK but not an empty EXTRACTION.
# --------------------------------------------------------------------------

CI_HYGIENE = COMMON / "ci-hygiene.md"


def test_ci_hygiene_fails_closed_on_zero_extracted_subjects() -> None:
    text = read(CI_HYGIENE)
    assert "empty walk" in text
    assert "empty EXTRACTION" in text
    assert "zero comparable subjects" in text


def test_ci_hygiene_requires_a_zero_subject_test_case() -> None:
    assert "readable but empty-of-subjects" in read(CI_HYGIENE)


# --------------------------------------------------------------------------
# D-wu-39 -- corroboration was never required to declare its SOURCE probe.
# --------------------------------------------------------------------------

SINGLE_SIGNAL = COMMON / "single-signal-verification.md"


def test_single_signal_requires_a_declared_source_probe() -> None:
    text = read(SINGLE_SIGNAL)
    assert "Declare the SOURCE probe" in text
    assert "source_probe" in text


def test_single_signal_binds_the_obligation_to_mechanized_gates() -> None:
    """A gate that treats an ABSENT source as "different, so independent"
    certifies a claim with zero declared measurements."""
    text = read(SINGLE_SIGNAL)
    assert "must treat a missing/empty source as a VIOLATION" in text
    assert "CONFIRMED`/`REFUTED" in text


# --------------------------------------------------------------------------
# D-wu-72 -- the rule's only named route is not installed by the documented copy.
# --------------------------------------------------------------------------

AGENTS_RULE = COMMON / "agents.md"

# Reference in the rule -> the repo artifact that satisfies it.
AGENTS_RULE_DEPENDENCIES = {
    "/start-task": Path("commands/start-task.md"),
    "AGENTS.md §5": Path("agent-self/config/AGENTS.md"),
}


@pytest.mark.parametrize(
    ("reference", "artifact"),
    sorted((k, v) for k, v in AGENTS_RULE_DEPENDENCIES.items()),
)
def test_agents_rule_names_the_artifact_behind_each_reference(
    reference: str, artifact: Path
) -> None:
    """`cp -r rules/common ~/.claude/rules/common` ships neither artifact, so a
    rule that names them without naming their source is a dangling pointer."""
    text = read(AGENTS_RULE)
    assert reference in text
    assert artifact.as_posix() in text
    assert (REPO_ROOT / artifact).is_file()


def test_agents_rule_points_at_the_agents_md_that_actually_has_a_section_5() -> None:
    harness_contract = read(REPO_ROOT / AGENTS_RULE_DEPENDENCIES["AGENTS.md §5"])
    assert re.search(r"^## 5\. ", harness_contract, re.M)
    # The repository-root AGENTS.md is the contributor guide and has no §5.
    assert not re.search(r"^## 5\. ", read(REPO_ROOT / "AGENTS.md"), re.M)
    assert "Not the repository-root `AGENTS.md`" in read(AGENTS_RULE)


# --------------------------------------------------------------------------
# D-wu-59 / D-wu-72 -- the deployed bundle mirror had drifted from canonical.
# --------------------------------------------------------------------------

# Scoped deliberately: only the two mirrors adjudicated here. The other shared
# rules/common files also differ from their bundle copies, but those belong to
# other findings and a blanket parity gate would assert beyond this evidence.
BUNDLE_MIRRORS_PINNED = ("performance.md", "agents.md")


@pytest.mark.parametrize("name", BUNDLE_MIRRORS_PINNED)
def test_bundle_mirror_matches_canonical(name: str) -> None:
    """`agent-self/bootstrap.ps1` force-copies the bundle over the live tree, so
    a bundle that has drifted DOWNGRADES a correct live rule on next bootstrap.
    """
    assert read(COMMON / name) == read(BUNDLE_COMMON / name)


def test_bundle_agents_mirror_has_no_phantom_agent_roster() -> None:
    """The stale mirror shipped a static roster whose `rust-reviewer` row had no
    backing definition -- the exact drift the canonical rule forbids."""
    text = read(BUNDLE_COMMON / "agents.md")
    assert "rust-reviewer" not in text
    assert "do NOT keep a static list" in text


def test_bundle_performance_mirror_keeps_the_opus_floor() -> None:
    text = read(BUNDLE_COMMON / "performance.md")
    assert "ALL substantive subagents" in text
    assert "Pair programming and code generation" not in text
