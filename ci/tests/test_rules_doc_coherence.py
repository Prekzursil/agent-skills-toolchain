"""Documentation-coherence gates for ``rules/`` (findings A023 and A048).

Two first-party contradictions shipped on main and were only visible by reading
two files side by side, so nothing in CI could catch them:

A023  ``rules/common/code-review.md`` mapped a HIGH finding to ``WARN`` and put
      only CRITICAL in ``Block``, while ``commands/code-review.md`` and
      ``commands/python-review.md`` both block on "CRITICAL or HIGH".  A review
      result holding exactly one HIGH and zero CRITICAL therefore had two
      mutually exclusive terminal decisions depending on which document the
      agent read.

A048  ``rules/perl/coding-style.md`` mandates ``Types::Standard`` for *all*
      Moo attributes, while the repository example in ``rules/perl/patterns.md``
      declared ``has dbh => (is => 'ro', required => 1);`` with no ``isa``.  An
      agent copying the first-party example produced rule-noncompliant Perl.

Both checks are DIRECTION-AGNOSTIC on purpose: they assert that the documents
agree, not that they agree on one particular answer.  Narrowing the Perl
mandate, or moving the Block boundary back to CRITICAL-only, stays legal --
provided every document moves together.

Scope measured (inline, not a footnote): the A023 check covers the rule plus
the two review COMMANDS in both the repo tree and the ``agent-self/config``
deploy mirror.  It deliberately does NOT cover ``agents/code-reviewer.md``,
which carries the same "Warning: HIGH issues only" wording at :209-211; that
file is a separate finding (D-a018) owned by another unit, and folding it in
here would make this gate red for a defect this change did not touch.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Every live document that declares the review Block boundary, except
# agents/code-reviewer.md -- see the scope note in the module docstring.
BOUNDARY_DOCS = (
    "rules/common/code-review.md",
    "commands/code-review.md",
    "commands/python-review.md",
    "agent-self/config/rules/common/code-review.md",
    "agent-self/config/commands/code-review.md",
    "agent-self/config/commands/python-review.md",
)

# The rule file whose severity table must agree with its own Approval Criteria.
SEVERITY_TABLE_DOCS = (
    "rules/common/code-review.md",
    "agent-self/config/rules/common/code-review.md",
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

FENCE = re.compile(r"^\s*```")
HAS_ATTR = re.compile(r"^\s*has\s+\S+\s*=>\s*\(")


def read(rel: str) -> str:
    path = REPO_ROOT / rel
    assert path.is_file(), f"missing document: {rel}"
    return path.read_text(encoding="utf-8")


def strip_fences(text: str) -> list[str]:
    """Prose lines only.

    Required, not cosmetic: ``commands/python-review.md`` ships an EXAMPLE
    report inside a fence that reads "Block merge until CRITICAL issue is
    fixed".  Scanned as policy it looks like a CRITICAL-only boundary and the
    detector reports a contradiction that does not exist.
    """
    out: list[str] = []
    inside = False
    for line in text.splitlines():
        if FENCE.match(line):
            inside = not inside
            continue
        if not inside:
            out.append(line)
    return out


def block_declarations(text: str) -> list[str]:
    """Prose lines that declare the Block outcome (contain 'Block' + CRITICAL)."""
    return [
        line.strip()
        for line in strip_fences(text)
        if re.search(r"\bBlock\b", line) and "CRITICAL" in line
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
# A023 -- the Block boundary must be one boundary
# --------------------------------------------------------------------------


def test_a023_every_document_agrees_on_whether_high_blocks() -> None:
    boundaries = {rel: high_blocks(rel) for rel in BOUNDARY_DOCS}
    assert len(set(boundaries.values())) == 1, (
        "the review Block boundary disagrees across first-party documents; a "
        "HIGH-only result has two terminal decisions: "
        + ", ".join(
            f"{rel}=" + ("HIGH-blocks" if blocks else "HIGH-warns-only")
            for rel, blocks in boundaries.items()
        )
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


def test_a023_example_report_inside_a_fence_is_not_read_as_policy() -> None:
    """The fence-stripper is load-bearing -- pin it."""
    text = read("commands/python-review.md")
    assert "Block merge until CRITICAL issue is fixed" in text
    assert not any(
        "Block merge until CRITICAL" in decl for decl in block_declarations(text)
    )


# --------------------------------------------------------------------------
# A048 -- first-party Perl examples must obey the Perl coding-style mandate
# --------------------------------------------------------------------------


def types_standard_is_mandated_for_all_attributes(rel: str) -> bool:
    return any(
        "Types::Standard" in line and "all attributes" in line
        for line in read(rel).splitlines()
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
