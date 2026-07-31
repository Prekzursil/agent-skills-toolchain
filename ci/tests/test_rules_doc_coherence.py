"""Documentation-coherence gates for ``rules/`` (findings A023 and A048).

Two first-party contradictions shipped on main and were only visible by reading
two files side by side, so nothing in CI could catch them:

A023  ``rules/common/code-review.md`` maps a HIGH finding to ``WARN`` and puts
      only CRITICAL in ``Block``, while ``commands/python-review.md`` and the
      Python/TypeScript reviewer agents block on "CRITICAL or HIGH".  A review
      result holding exactly one HIGH and zero CRITICAL therefore had two
      mutually exclusive terminal decisions depending on which document the
      agent read.

A048  ``rules/perl/coding-style.md`` mandates ``Types::Standard`` for *all*
      Moo attributes, while the repository example in ``rules/perl/patterns.md``
      declared ``has dbh => (is => 'ro', required => 1);`` with no ``isa``.  An
      agent copying the first-party example produced rule-noncompliant Perl.

HISTORY OF THIS FILE, stated inline because it changes how the A023 check is
written.  An earlier version of this gate (unit C36, commit 1752e6f) required
all six boundary documents to give the SAME answer, and resolved the conflict by
flipping the rule to "HIGH blocks".  That collided head-on with unit C31
(8ebfd6e), which resolved it the other way, and C36 was reverted (f9bde20).  The
A023 check below is rewritten to the LAYERED model the repository actually
declares, rather than to either unit's flat "everyone must agree":

  * ``rules/common/code-review.md`` is the GENERAL single source of truth for
    the outcome -- ``commands/code-review.md`` says so in its own text -- and it
    grades a HIGH-only review as ``WARN``.  Every GENERAL surface must match it.
  * ``rules/README.md`` -> "Rule Priority" lets a LANGUAGE-specific rule be
    stricter.  A Python or TypeScript surface may block on HIGH, but it must
    SAY that it is a deliberate override, and -- per ``rules/README.md``:160-164,
    which notes that the README itself is scoped ``**/*.__never_load__`` and so
    never enters a model's context -- the common rule must record the override
    next to the row it qualifies, or the conflict is unresolvable at the point
    of use.

That is three tests instead of one, and it is direction-agnostic in the same way
the original was: it does not require HIGH to warn, it requires the GENERAL
surfaces to agree with the rule and every stricter surface to be declared.  If
the owner later rules that HIGH blocks everywhere, flip the rule's severity
table and Approval Criteria, drop the language overrides, and these tests stay
meaningful.

Scope measured (inline, not a footnote): the A023 checks cover the rule, both
review commands, both reviewer agents, the general reviewer agent, and the
``source-command-python-review`` skill in both dual-write locations -- in the
repo tree and, where a mirror exists, in the ``agent-self/config`` deploy copy.
Not covered: any surface that states the boundary only inside a fenced example.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# GENERAL surfaces.  These must agree with the rule's severity table, which
# grades a HIGH-only review as WARN.
GENERAL_BOUNDARY_DOCS = (
    "rules/common/code-review.md",
    "commands/code-review.md",
    "agents/code-reviewer.md",
    "agent-self/config/rules/common/code-review.md",
    "agent-self/config/commands/code-review.md",
)

# LANGUAGE-specific surfaces.  These are allowed to be stricter than the general
# rule, but only if they declare the override in their own text.
LANGUAGE_BOUNDARY_DOCS = (
    "commands/python-review.md",
    "agents/python-reviewer.md",
    "agents/typescript-reviewer.md",
    "agent-self/config/commands/python-review.md",
    ".agents/skills/source-command-python-review/SKILL.md",
    "skills/source-command-python-review/SKILL.md",
)

# The rule file whose severity table must agree with its own Approval Criteria,
# and which must carry the inline record of every language override.
SEVERITY_TABLE_DOCS = (
    "rules/common/code-review.md",
    "agent-self/config/rules/common/code-review.md",
)

# Every language-specific surface named above must be findable by name in the
# common rule's Language note, so an agent that loads only the rule still learns
# that these paths are stricter.
OVERRIDE_NAMES_RECORDED_IN_THE_RULE = (
    "agents/python-reviewer.md",
    "commands/python-review.md",
    "source-command-python-review",
    "agents/typescript-reviewer.md",
)

DECLARED_OVERRIDE = "deliberately STRICTER"

FENCE = re.compile(r"^\s*```")
QUOTE = re.compile(r"^\s*>")
HAS_ATTR = re.compile(r"^\s*has\s+\S+\s*=>\s*\(")
# Case-INSENSITIVE on purpose.  C31 phrases the general outcome as
# "**CRITICAL** -> **BLOCK** the commit"; a case-sensitive r"\bBlock\b" misses
# it entirely and the detector then raises "no Block declaration found" instead
# of reporting a boundary.  test_a023_case_sensitive_detector_would_miss_c31
# pins that, so nobody re-tightens it.
BLOCK_WORD = re.compile(r"\bBlock\b", re.IGNORECASE)


def read(rel: str) -> str:
    path = REPO_ROOT / rel
    assert path.is_file(), f"missing document: {rel}"
    return path.read_text(encoding="utf-8")


def policy_lines(text: str) -> list[str]:
    """Lines that state policy: no fenced blocks, no blockquotes.

    Both exclusions are load-bearing, not cosmetic:

    * ``commands/python-review.md`` ships an EXAMPLE report inside a fence that
      reads "Block merge until CRITICAL issue is fixed".  Scanned as policy it
      looks like a CRITICAL-only boundary and the detector reports a
      contradiction that does not exist.
    * ``rules/common/code-review.md`` carries the language-override marker as a
      blockquote annotation that necessarily *describes* both outcomes ("no
      CRITICAL is a WARN, not a block ... surfaces MAY be stricter and block on
      HIGH").  Read as policy that single note self-contradicts.  A blockquote
      annotates the policy above it; it is not itself a verdict row.
    """
    out: list[str] = []
    inside = False
    for line in text.splitlines():
        if FENCE.match(line):
            inside = not inside
            continue
        if inside or QUOTE.match(line):
            continue
        out.append(line)
    return out


def block_declarations(text: str) -> list[str]:
    """Policy lines that declare the Block outcome (say 'Block' AND CRITICAL)."""
    return [
        line.strip()
        for line in policy_lines(text)
        if BLOCK_WORD.search(line) and "CRITICAL" in line
    ]


def high_blocks(rel: str) -> bool:
    decls = block_declarations(read(rel))
    assert decls, f"{rel}: no Block declaration found -- detector is broken"
    verdicts = {"HIGH" in d for d in decls}
    assert len(verdicts) == 1, f"{rel}: self-contradictory Block declarations: {decls}"
    return verdicts.pop()


def severity_table_action(rel: str, level: str) -> str:
    """The bolded action word for one severity row of the review severity table."""
    for line in read(rel).splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 4 and cells[1] == level:
            match = re.search(r"\*\*([A-Z]+)\*\*", cells[3])
            assert match, f"{rel}: {level} row has no bolded action: {line!r}"
            return match.group(1)
    raise AssertionError(f"{rel}: no severity-table row for {level}")


def perl_code_blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] | None = None
    is_perl = False
    for line in text.splitlines():
        if FENCE.match(line):
            if current is None:
                is_perl = line.strip() == "```perl"
                current = []
            else:
                if is_perl:
                    blocks.append(current)
                current = None
                is_perl = False
            continue
        if current is not None:
            current.append(line)
    return blocks


def moo_attributes(block: list[str]) -> list[str]:
    """Whole ``has ... );`` statements, re-joined so multi-line forms are seen."""
    statements: list[str] = []
    buffer: list[str] | None = None
    for line in block:
        if buffer is None and HAS_ATTR.match(line):
            buffer = [line]
        elif buffer is not None:
            buffer.append(line)
        if buffer is not None and ");" in buffer[-1]:
            statements.append(" ".join(part.strip() for part in buffer))
            buffer = None
    if buffer is not None:
        statements.append(" ".join(part.strip() for part in buffer))
    return statements


# --------------------------------------------------------------------------
# A023 -- one GENERAL boundary, and every stricter surface declared
# --------------------------------------------------------------------------


def test_a023_general_surfaces_agree_with_the_rule() -> None:
    """No GENERAL surface may restate the boundary differently from the rule."""
    boundaries = {rel: high_blocks(rel) for rel in GENERAL_BOUNDARY_DOCS}
    assert len(set(boundaries.values())) == 1, (
        "the review Block boundary disagrees across GENERAL first-party "
        "documents; a HIGH-only result has two terminal decisions: "
        + ", ".join(
            f"{rel}=" + ("HIGH-blocks" if blocks else "HIGH-warns-only")
            for rel, blocks in boundaries.items()
        )
    )


@pytest.mark.parametrize("rel", LANGUAGE_BOUNDARY_DOCS)
def test_a023_a_stricter_language_surface_declares_its_override(rel: str) -> None:
    """A language surface may be stricter than the rule -- silently, never."""
    if high_blocks(rel) == high_blocks("rules/common/code-review.md"):
        pytest.skip(f"{rel} matches the general rule; nothing to declare")
    assert DECLARED_OVERRIDE in read(rel), (
        f"{rel} blocks on HIGH while rules/common/code-review.md grades HIGH as "
        f"WARN, but it never says the divergence is deliberate. Add the "
        f"{DECLARED_OVERRIDE!r} precedence note, or conform to the rule."
    )


@pytest.mark.parametrize("rel", SEVERITY_TABLE_DOCS)
def test_a023_the_rule_records_every_language_override_inline(rel: str) -> None:
    """rules/README.md:160-164 -- the README never loads, so the rule must carry it."""
    text = read(rel)
    assert "Language note" in text, (
        f"{rel}: no inline Language note. rules/README.md is scoped "
        "'**/*.__never_load__', so an override recorded only there is invisible "
        "at the point of use."
    )
    missing = [name for name in OVERRIDE_NAMES_RECORDED_IN_THE_RULE if name not in text]
    assert not missing, (
        f"{rel}: Language note does not name the stricter surfaces {missing}"
    )


@pytest.mark.parametrize("rel", SEVERITY_TABLE_DOCS)
def test_a023_severity_table_agrees_with_approval_criteria(rel: str) -> None:
    action = severity_table_action(rel, "HIGH")
    assert action in {"BLOCK", "WARN"}, f"{rel}: unexpected HIGH action {action!r}"
    assert (action == "BLOCK") == high_blocks(rel), (
        f"{rel}: severity table says HIGH -> {action} but the Approval Criteria "
        f"say HIGH {'blocks' if high_blocks(rel) else 'does not block'}"
    )


@pytest.mark.parametrize("rel", SEVERITY_TABLE_DOCS)
def test_a023_critical_always_blocks(rel: str) -> None:
    """Anti-regression floor: no coherence fix may relax CRITICAL."""
    assert severity_table_action(rel, "CRITICAL") == "BLOCK"


def test_a023_detector_fires_on_the_known_broken_wording(tmp_path: Path) -> None:
    """Both-states check: the parser must FAIL the pre-fix text, not just pass."""
    broken = tmp_path / "broken.md"
    broken.write_text(
        "## Approval Criteria\n\n"
        "- **Approve**: No CRITICAL or HIGH issues\n"
        "- **Warning**: Only HIGH issues (merge with caution)\n"
        "- **Block**: CRITICAL issues found\n",
        encoding="utf-8",
    )
    assert block_declarations(broken.read_text(encoding="utf-8")) == [
        "- **Block**: CRITICAL issues found"
    ]
    assert "HIGH" not in block_declarations(broken.read_text(encoding="utf-8"))[0]


def test_a023_case_sensitive_detector_would_miss_c31() -> None:
    """Known-broken control: this is the exact bug the revert message named."""
    c31 = "   - **CRITICAL** -> **BLOCK** the commit. Must be fixed before merge."
    assert re.search(r"\bBlock\b", c31) is None, "control invalid: no longer a miss"
    assert BLOCK_WORD.search(c31) is not None, "the shipped detector must see it"


def test_a023_example_report_inside_a_fence_is_not_read_as_policy() -> None:
    """The fence-stripper is load-bearing -- pin it."""
    text = read("commands/python-review.md")
    assert "Block merge until CRITICAL issue is fixed" in text
    assert not any(
        "Block merge until CRITICAL" in decl for decl in block_declarations(text)
    )


def test_a023_blockquote_annotation_is_not_read_as_policy() -> None:
    """The blockquote-stripper is load-bearing too -- pin it with both states."""
    annotated = (
        "- **Block**: CRITICAL issues found\n"
        "> a review holding HIGH but no CRITICAL is a WARN, not a block\n"
    )
    assert block_declarations(annotated) == ["- **Block**: CRITICAL issues found"]
    naive = [
        line.strip()
        for line in annotated.splitlines()
        if BLOCK_WORD.search(line) and "CRITICAL" in line
    ]
    assert len(naive) == 2, "control invalid: the naive scan no longer double-counts"


# --------------------------------------------------------------------------
# A048 -- first-party Perl examples must obey the Perl coding-style mandate
# --------------------------------------------------------------------------


def types_standard_is_mandated_for_all_attributes(rel: str) -> bool:
    return any(
        "Types::Standard" in line and "all attributes" in line
        for line in read(rel).splitlines()
    )


PERL_MANDATE_DOCS = (
    "rules/perl/coding-style.md",
    "agent-self/config/rules/perl/coding-style.md",
)

PERL_EXAMPLE_DOCS = (
    "rules/perl/patterns.md",
    "rules/perl/security.md",
    "rules/perl/testing.md",
    "rules/perl/hooks.md",
    "agent-self/config/rules/perl/patterns.md",
    "agent-self/config/rules/perl/security.md",
    "agent-self/config/rules/perl/testing.md",
    "agent-self/config/rules/perl/hooks.md",
)


@pytest.mark.parametrize("rel", PERL_MANDATE_DOCS)
def test_a048_mandate_is_still_stated(rel: str) -> None:
    """Detector sanity: if this goes False the example check below is vacuous."""
    assert types_standard_is_mandated_for_all_attributes(rel)


@pytest.mark.parametrize("rel", PERL_EXAMPLE_DOCS)
def test_a048_every_example_moo_attribute_is_type_constrained(rel: str) -> None:
    style = rel.rsplit("/", 1)[0] + "/coding-style.md"
    if not types_standard_is_mandated_for_all_attributes(style):
        pytest.skip("the all-attributes mandate was narrowed; examples are exempt")
    for block in perl_code_blocks(read(rel)):
        attributes = moo_attributes(block)
        if not attributes:
            continue
        for statement in attributes:
            assert "isa =>" in statement, (
                f"{rel}: first-party example attribute has no Types::Standard "
                f"constraint while coding-style.md mandates one: {statement}"
            )
        assert any("use Types::Standard" in line for line in block), (
            f"{rel}: example uses isa => but never imports Types::Standard, so "
            "copying it verbatim does not compile"
        )


def test_a048_detector_finds_the_attributes_it_claims_to_check() -> None:
    """Control: the parser must actually see the repository example."""
    blocks = perl_code_blocks(read("rules/perl/patterns.md"))
    statements = [stmt for block in blocks for stmt in moo_attributes(block)]
    assert any("has dbh" in stmt for stmt in statements), statements
    assert len(statements) >= 4, statements


def test_a048_detector_fires_on_the_known_broken_example() -> None:
    """Both-states check for the Perl parser."""
    broken = ["package X;", "use Moo;", "", "has dbh => (is => 'ro', required => 1);"]
    statements = moo_attributes(broken)
    assert statements == ["has dbh => (is => 'ro', required => 1);"]
    assert "isa =>" not in statements[0]
