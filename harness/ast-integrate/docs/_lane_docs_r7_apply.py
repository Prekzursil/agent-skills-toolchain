"""Round 7: apply the corrections, preserving each file's own line endings.

Every edit is exact-match and fails CLOSED: an anchor not found exactly once
aborts the whole run before anything is written. The line-ending style is
MEASURED per file and re-emitted unchanged -- an earlier probe this round
reported all three carriers as 100% CRLF and a raw byte census showed CR=0 on
every one of them, so assuming either style would have turned a small edit into
a whole-file diff.

Terminal state: SUCCESS:docs-r7-apply / FAILED:docs-r7-apply <reason>
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

TEST_FILE = "ci/tests/test_command_doc_promises.py"
R6_DOC = "docs/_LANE-DOCS-BUILD-R6.md"

ROUND7_MARKER = "# Round 7 arm:"

TOP_IMPORT_ANCHOR = "import pytest\nimport io\n"
TOP_IMPORT_NEW = (
    "import pytest\nimport io\n\nfrom docs_count_anchors import ROUND5_COUNT_ANCHORS\n"
)

NEW_ARM = '''

# --------------------------------------------------------------------------
# Round 7 arm: the round-5 surface counts must keep their commit anchors
# --------------------------------------------------------------------------
#
# Round 5 shipped the pair "20 bare refs / 16 unresolved" with no anchor, in two
# files. It had already gone stale by one when it was committed; an audit refuted
# it; round 6 fixed both sentences by pinning each number to the immutable commit
# it was measured at. Nothing yet stopped a later edit from stripping the anchor
# back off -- which is exactly how the defect arrived the first time.
#
# This arm pins the ANCHOR, not the number. Pinning the number would re-create
# the defect, because a count tied to HEAD moves on every sibling commit.
#
# WHY THE EXPECTED SHAS LIVE IN ANOTHER MODULE
# --------------------------------------------
# The first version of this arm held them in a constant HERE -- inside one of the
# files it checks. ``docs/_lane_docs_r7_bothstates.py`` mutated the real file and
# proved that version INERT: stripping the anchor from the carrier also stripped
# it from the constant, so the expectation moved with the thing it was expecting
# and the gate stayed GREEN on a genuinely broken file. A gate whose expected
# value lives inside the artifact under test cannot detect that value's removal.
#
# It is deliberately cheap -- two file reads, no git history walk. That is the
# point: this suite runs in a checkout with fetch-depth 1, where a history walk
# fails closed. Re-deriving the counts themselves DOES need full history, so it
# stays an on-demand probe. Both states are measured in
# docs/_LANE-DOCS-BUILD-R7.md.
#
# SCOPE, stated so the arm is not read as wider than it is: it proves an anchor
# survives in the REGION that states the counts. It does not prove that every
# number in either file is anchored, nor that the anchor names the right commit
# -- the on-demand probe settles that.

#: The module holding the expected SHAs. MUST NOT be a carrier; a control pins it.
ANCHOR_SOURCE = "ci/tests/docs_count_anchors.py"

#: Tracked files that state the round-5 surface counts.
COUNT_CARRIERS = (
    "ci/tests/test_command_doc_promises.py",
    "docs/_LANE-DOCS-BUILD-R5.md",
)


def _carrier_source(rel: str) -> str:
    """Read a carrier with ``newline=""`` so its line endings survive verbatim."""
    return io.open((REPO_ROOT / rel), encoding="utf-8", newline="").read()


def _count_region(rel: str, source: str) -> str:
    """The slice of a carrier that states the round-5 surface counts.

    Scoping to a REGION rather than the whole file is load-bearing: both SHAs
    appear elsewhere in these files (in prose about the correction), so a
    whole-file search would pass even after the count itself lost its anchor.
    """
    lines = source.splitlines()
    if rel.endswith(".md"):
        for line in lines:
            if line.lstrip().startswith("| **R5-5** |"):
                return line
        raise AssertionError(f"{rel}: row R5-5 is gone, and it carried the counts")

    start = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("# Round 5 arm:"):
            start = i
            break
    if start is None:
        raise AssertionError(f"{rel}: the round-5 banner comment is gone")

    block: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            block.append(line)
        else:
            break
    return "\\n".join(block)


def _missing_anchors(region: str) -> list[str]:
    return [sha for sha in ROUND5_COUNT_ANCHORS if sha not in region]


def test_round5_counts_keep_their_commit_anchors() -> None:
    """The gate proper: neither carrier may state the counts unanchored."""
    offenders = {}
    for rel in COUNT_CARRIERS:
        missing = _missing_anchors(_count_region(rel, _carrier_source(rel)))
        if missing:
            offenders[rel] = missing
    assert not offenders, (
        "a round-5 surface count lost the commit it was measured at, which is how "
        "it reads as CURRENT and goes stale:\\n"
        + "\\n".join(f"  {rel} -> missing {missing}" for rel, missing in offenders.items())
    )


def test_control_the_expectation_does_not_live_in_a_carrier() -> None:
    """The control that the first version of this arm failed.

    H1: the expectation is independent of the artifact -> stripping an anchor
    from a carrier leaves ROUND5_COUNT_ANCHORS intact and the gate fires.
    H2: the expectation lives in the carrier -> it is stripped too and the gate
    stays green. The two give different answers only if this holds.
    """
    assert ANCHOR_SOURCE not in COUNT_CARRIERS, (
        f"{ANCHOR_SOURCE} became one of the files it is the expectation for; "
        "the gate is now inert -- see docs/_lane_docs_r7_bothstates.py"
    )
    assert ROUND5_COUNT_ANCHORS, "the expectation module declares no anchors"


def test_control_anchor_arm_fires_when_an_anchor_is_stripped() -> None:
    """Every anchor, every carrier: removing it must be detected."""
    for rel in COUNT_CARRIERS:
        source = _carrier_source(rel)
        for sha in ROUND5_COUNT_ANCHORS:
            broken = source.replace(sha, "")
            assert sha in _missing_anchors(_count_region(rel, broken)), (
                f"{rel}: stripping {sha} did not make the arm fire -- it is "
                "reading something other than the region that carries the count"
            )


def test_control_anchor_arm_is_silent_on_the_shipped_text() -> None:
    """The other direction: the arm must not fire on the state we ship."""
    for rel in COUNT_CARRIERS:
        assert _missing_anchors(_count_region(rel, _carrier_source(rel))) == []


def test_control_the_region_is_not_the_whole_file() -> None:
    """A region equal to the whole file would make the check trivially green."""
    rel = "ci/tests/test_command_doc_promises.py"
    source = _carrier_source(rel)
    marker = "WHY THE RESOLVER IS MULTI-ROOT"
    assert marker in source, "precondition: the module docstring still says this"
    assert marker not in _count_region(rel, source), (
        "the extracted region swallowed the module docstring; it is not scoped "
        "to the comment block that carries the counts"
    )


def test_control_anchor_arm_is_eol_agnostic() -> None:
    """A CRLF working tree and an LF blob must produce the same verdict."""
    for rel in COUNT_CARRIERS:
        lf = _carrier_source(rel).replace("\\r\\n", "\\n")
        crlf = lf.replace("\\n", "\\r\\n")
        assert _missing_anchors(_count_region(rel, lf)) == _missing_anchors(
            _count_region(rel, crlf)
        ), f"{rel}: the arm's verdict depends on line endings"
'''

# (anchor, replacement) -- each must occur exactly once.
R6_EDITS = [
    (
        "**NO — structurally unrunnable there, and too slow**",
        '**NO — but "structurally unrunnable" is REFUTED; see the round-7 correction. '
        "The decision survives, the reason does not**",
    ),
    (
        "It stays an on-demand re-derivation. |",
        "It stays an on-demand re-derivation. "
        "*Correction (round 7): the verdict wording was **REFUTED**. Measured with a "
        "two-arm clone control (`docs/_lane_docs_r7_shallow_control.py`): a depth-1 clone "
        "fails closed exactly as claimed, and the SAME clone after `fetch --unshallow` "
        "returns `SUCCESS:docs-r6-pinned pre_fix=20/16 post_fix=19/15`. So the probe is not "
        "structurally unrunnable in CI; it needs `fetch-depth: 0`, a two-line setting that "
        "**6 workflows in this repo already carry as a live YAML field — including "
        "`quality.yml` itself**, in a different job. The decision not to wire it SURVIVES on "
        "a reason round 6 did not give: the probe's inputs are two immutable commits, so its "
        "answer is frozen and a gate on it can never go red because reality changed, only "
        "because the probe or the checkout broke. The defect that actually recurred is the "
        "anchor being stripped off the sentence, and that is checkable in milliseconds with "
        "no history at all — which is what round 7 shipped instead.* |",
    ),
    (
        "**Why it is not wired into CI** — two independent measurements, not a preference "
        "(see R6-7): the\nhosting job's checkout is shallow, so the pinned commits would not "
        "exist; and 33.5 s is not a\nper-PR gate.",
        "**Why it is not wired into CI** — *rewritten in round 7. The original reasoning is "
        "kept below because it was REFUTED, not merely improved.* The probe reads two "
        "IMMUTABLE commits, so its verdict is frozen: a CI gate on it cannot detect a new "
        "defect, only its own breakage. That is the surviving reason.\n\n"
        'REFUTED wording (round 6): *"two independent measurements, not a preference (see '
        "R6-7): the hosting job's checkout is shallow, so the pinned commits would not exist; "
        'and 33.5 s is not a per-PR gate."* The first is true as a PREMISE and false as the '
        "CONCLUSION drawn from it — a depth-1 clone does fail closed (re-measured), but "
        "`fetch-depth: 0` is the remedy and 6 workflows here already set it, one of them "
        "`quality.yml`. The second was only ever a Windows measurement (re-timed at 27.8 s) "
        "and was never taken on a Linux runner.",
    ),
    (
        "6. **The 33.5 s pinned probe is on-demand only.** If the docs steps ever move to a "
        "job with\n   `fetch-depth: 0`, re-evaluate; today they do not.",
        "6. **The pinned probe is on-demand only** — for the frozen-input reason in §4, not "
        "for the\n   shallow-checkout reason round 6 gave, which round 7 REFUTED. Nor is "
        '"the docs steps\n   moving" the precondition: adding `fetch-depth: 0` to the '
        "hosting job would be, and that\n   is a deliberate cost (full history on the "
        "repo's largest job) bought for a frozen answer.",
    ),
]


def eol_of(raw: str) -> str | None:
    """The file's uniform line ending, or None if it is mixed or absent.

    Measured, never assumed. An earlier probe this round reported all three
    carriers as 100% CRLF; a raw byte census showed CR=0 on every one. The tell
    was that the broken probe returned a count exactly equal to each file's line
    total -- suspiciously equal numbers are a collection-level mistake far more
    often than genuine parity.
    """
    lf_total = raw.count("\n")
    cr_total = raw.count("\r")
    crlf = raw.count("\r\n")
    if lf_total == 0:
        return None
    if cr_total == 0:
        return "\n"
    if crlf == lf_total == cr_total:
        return "\r\n"
    return None


def load(rel: str) -> tuple[str, str | None]:
    raw = (REPO / rel).read_bytes().decode("utf-8")
    return raw, eol_of(raw)


def save(rel: str, text_lf: str, eol: str) -> None:
    (REPO / rel).write_bytes(text_lf.replace("\n", eol).encode("utf-8"))


def main() -> int:
    plan: list[tuple[str, str, str]] = []

    eols: dict[str, str] = {}
    for rel in (TEST_FILE, R6_DOC):
        _, eol = load(rel)
        if eol is None:
            print(
                f"FAILED:docs-r7-apply {rel} has mixed or absent line endings; refusing"
            )
            return 1
        eols[rel] = eol

    # ---- 1. the gate arm: one import at the top, the arm at the bottom ------
    src, _ = load(TEST_FILE)
    lf = src.replace("\r\n", "\n")
    if ROUND7_MARKER in lf:
        print(
            "FAILED:docs-r7-apply the round-7 arm is already present; refusing to re-apply"
        )
        return 1
    if lf.count(TOP_IMPORT_ANCHOR) != 1:
        print(
            f"FAILED:docs-r7-apply import anchor occurs {lf.count(TOP_IMPORT_ANCHOR)}x (want 1)"
        )
        return 1
    lf = lf.replace(TOP_IMPORT_ANCHOR, TOP_IMPORT_NEW, 1)
    plan.append(
        (TEST_FILE, lf.rstrip("\n") + "\n" + NEW_ARM.lstrip("\n"), eols[TEST_FILE])
    )

    # ---- 2. the four round-6 sentence corrections ---------------------------
    doc, _ = load(R6_DOC)
    doc_lf = doc.replace("\r\n", "\n")
    for anchor, replacement in R6_EDITS:
        hits = doc_lf.count(anchor)
        if hits != 1:
            print(
                f"FAILED:docs-r7-apply anchor occurs {hits}x (want 1): {anchor[:70]!r}"
            )
            return 1
        doc_lf = doc_lf.replace(anchor, replacement, 1)
    plan.append((R6_DOC, doc_lf, eols[R6_DOC]))

    # ---- write only after every edit resolved -------------------------------
    for rel, text, eol in plan:
        save(rel, text, eol)

    for rel, _, eol in plan:
        _, got = load(rel)
        if got != eol:
            print(f"FAILED:docs-r7-apply {rel} changed line-ending style on write")
            return 1

    styles = ",".join(
        f"{rel.rsplit('/', 1)[-1]}={'LF' if e == chr(10) else 'CRLF'}"
        for rel, _, e in plan
    )
    print(
        f"SUCCESS:docs-r7-apply files={len(plan)} r6_edits={len(R6_EDITS)} eol[{styles}]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
