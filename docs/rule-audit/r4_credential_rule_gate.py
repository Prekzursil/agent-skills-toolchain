"""R4 gate: the DEPLOY SOURCE must not invert the credential-lifecycle non-negotiable.

WHAT IS WRONG RIGHT NOW
-----------------------
``agent-self/config/AGENTS.md`` is force-copied over ``~/.claude`` by ``bootstrap.ps1:45``
(``Copy-Item (Join-Path $Self 'config\\*') $ClaudeHome -Recurse -Force``). Measured across
rounds 1-3 and re-measured here:

* live ``~/.claude/AGENTS.md:113`` carries the §9 bullet **"NEVER remove, rotate, revoke,
  regenerate, unset or otherwise MODIFY any API key or token."** The deploy source carries it
  ZERO times -- the bullet is absent, not reworded.
* live §9b ``:142-144`` says a leaked secret must be reported and **"leave the rotation to the
  owner"**. The deploy source's §9b ``:131`` ends **"rotate, don't just delete"** -- an
  instruction to DO the banned action.

So one ``pwsh agent-self/bootstrap.ps1`` replaces an always-on security non-negotiable with its
inverse. ``AGENTS.md`` §10 ranks §9 above every lower layer precisely so no layer can relax it;
this relaxes it by deploying over it.

WHY THIS FILE EXISTS RATHER THAN A FIX
--------------------------------------
``AGENTS.md`` is propose-only for the RULERESEARCH lane, so the correction is the owner's.
Through three rounds the finding was tracked in PROSE while a LOWER-severity out-of-scope defect
had a mechanical tracker (``r2_pathrefs.KNOWN_DEFECTS``) -- the round-3 adversary called that out
as residual 4. This is the missing tracker. It changes nothing; it makes the state measurable, and
it turns GREEN by itself on the day the owner fixes the deploy source, which is the property a
prose note does not have.

DESIGN
------
Two invariants on the deploy source, asserted independently of the live tree so the gate still
means something in a clone where ``~/.claude`` does not exist:

    INV-1  a §9 bullet forbidding the agent to rotate/revoke/regenerate a credential is PRESENT
    INV-2  no imperative telling the agent to rotate it is present

plus a THIRD, live-only arm that diffs the deploy source's §9 against the live §9 when
``~/.claude/AGENTS.md`` exists. Absent live tree => that arm reports SKIPPED, never PASSED: a
check that could not run is not a check that passed.

Every arm has a both-states control built from the REAL text, and there is a positive control
proving the section extractor can find a section that exists -- without it, "section not found"
and "section clean" are the same silence.

Exit codes: 0 = the deploy source is safe. 1 = it is inverted (the state TODAY). 2 = the gate
could not measure (missing file, empty section), which is a broken gate, not a pass.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEPLOY_SOURCE = REPO / "agent-self" / "config" / "AGENTS.md"
LIVE = Path.home() / ".claude" / "AGENTS.md"

# The protective bullet, in the loosest form that still means "the agent must not do it".
PROTECTIVE = re.compile(
    r"NEVER\s+(?:remove|rotate|revoke|regenerate)[^.\n]*\b(?:key|token|credential)",
    re.I,
)
# The inversion: an imperative to rotate, as opposed to a description of the owner rotating.
INVERSION = re.compile(
    r"\brotate,?\s+(?:don'?t|do not|rather than)\s+just\s+delete", re.I
)
# The live wording that makes ownership explicit; used by the live-only arm.
OWNER_ROTATES = re.compile(r"leave the rotation to the owner", re.I)


def section(text: str, heading: str) -> str | None:
    """The body of one ``## <heading>`` block, or None if the heading is not there.

    The terminator is ``(?=\\s|$)``, NOT ``\\b``. The first version used ``\\b`` after
    ``re.escape("9.")`` and matched nothing at all: between ``.`` and the following space there
    are two non-word characters, so there is no word boundary there. Every arm then reported
    "no §9 section", which is the shape where a broken extractor and a clean document produce
    the same silence -- caught only because this gate carries a POSITIVE control asserting that
    a section which really exists is found.
    """
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}(?=\s|$).*?$(.*?)(?=^##\s|\Z)", re.M | re.S
    )
    match = pattern.search(text)
    return match.group(1) if match else None


def audit(text: str) -> list[str]:
    """Violations of the two source-side invariants. Pure, so a mutant can be fed to it."""
    bad: list[str] = []
    nine = section(text, "9.")
    nine_b = section(text, "9b.")
    if nine is None:
        return ["section-missing: no '## 9.' security section at all"]
    if not PROTECTIVE.search(nine):
        bad.append(
            "INV-1 the §9 bullet forbidding the agent to rotate/revoke/regenerate a "
            "credential is ABSENT from the deploy source"
        )
    scope = nine + (nine_b or "")
    if INVERSION.search(scope):
        bad.append(
            "INV-2 §9/§9b instructs the agent to rotate ('rotate, don't just delete'), "
            "which is the banned action"
        )
    return bad


def live_arm(source: str) -> tuple[str, list[str]]:
    """Compare against the live contract when it exists. SKIPPED is not PASSED."""
    if not LIVE.exists():
        return "SKIPPED", []
    live_text = LIVE.read_text(encoding="utf-8")
    live_nine = section(live_text, "9.")
    if live_nine is None or not PROTECTIVE.search(live_nine):
        return (
            "UNUSABLE",
            [
                "the live §9 does not carry the protective bullet either, so it cannot be "
                "used as the reference -- resolve which copy is authoritative first"
            ],
        )
    bad: list[str] = []
    if not PROTECTIVE.search(section(source, "9.") or ""):
        bad.append(
            "live §9 carries the protective bullet and the deploy source does not"
        )
    live_b = section(live_text, "9b.") or ""
    src_b = section(source, "9b.") or ""
    if OWNER_ROTATES.search(live_b) and not OWNER_ROTATES.search(src_b):
        bad.append(
            "live §9b says to leave rotation to the owner; the deploy source omits that"
        )
    return "RAN", bad


def controls(source: str) -> list[str]:
    """Both-states, built from the real text so they cannot rot into decoration."""
    failures: list[str] = []

    def expect(label: str, got: object, want: object) -> None:
        print(f"  {'PASS' if got == want else 'FAIL'}  control {label}: got {got!r}")
        if got != want:
            failures.append(label)

    # Positive control for the extractor: a section that EXISTS must be found and be non-empty.
    nine = section(source, "9.")
    expect("extractor finds §9", bool(nine and nine.strip()), True)
    expect(
        "extractor returns None for a section that is absent",
        section(source, "99z."),
        None,
    )

    # A repaired copy must go clean, and each invariant must fire on its own falsification.
    repaired = source.replace(
        "## 9. Security non-negotiables",
        "## 9. Security non-negotiables\n\n- **NEVER remove, rotate, revoke, regenerate, unset "
        "or otherwise MODIFY any API key or token.**\n",
        1,
    ).replace(
        "rotate, don't just delete", "report it and leave the rotation to the owner"
    )
    expect("a repaired deploy source scores clean", audit(repaired), [])
    expect(
        "INV-1 fires when the bullet is removed again",
        any(
            "INV-1" in v
            for v in audit(repaired.replace("NEVER remove, rotate", "Please rotate"))
        ),
        True,
    )
    # INV-2's mutant is INJECTED, not string-swapped. It used to be built by replacing
    # "report it and leave the rotation to the owner" -- a phrase that exists only because the
    # `repaired` scaffold above put it there, and only while the real source still contained
    # "rotate, don't just delete" for that scaffold to swap. The day the deploy source was
    # actually repaired (2026-08-14) both replaces became no-ops, the mutant came out identical
    # to `repaired`, INV-2 did not fire, and this control failed -- while the gate itself was
    # working perfectly. A control coupled to its own scaffolding measures the scaffolding.
    #
    # Anchoring on the "## 9." heading instead is safe in both states: the positive control
    # above already asserts that section exists and is non-empty, and `audit()` scopes INV-2 to
    # §9 + §9b, so a bullet placed directly under the heading is always in scope.
    inverted = repaired.replace(
        "## 9. Security non-negotiables",
        "## 9. Security non-negotiables\n\n- On a leak: rotate, don't just delete.\n",
        1,
    )
    expect(
        "INV-2 fires when the inversion is re-introduced",
        any("INV-2" in v for v in audit(inverted)),
        True,
    )
    expect(
        "a document with no §9 at all is UNMEASURABLE, not clean",
        audit("# unrelated document\n\n## 1. Something\n\ntext\n") != [],
        True,
    )
    return failures


def main() -> int:
    if not DEPLOY_SOURCE.exists():
        print(
            f"FAILED:r4_credential_rule_gate {DEPLOY_SOURCE} is missing -- fail closed"
        )
        return 2
    source = DEPLOY_SOURCE.read_text(encoding="utf-8")
    if len(source) < 500:
        print(
            "FAILED:r4_credential_rule_gate deploy source is implausibly small -- fail closed"
        )
        return 2

    broken_controls = controls(source)
    if broken_controls:
        print(f"FAILED:r4_credential_rule_gate own controls failed: {broken_controls}")
        return 2

    violations = audit(source)
    status, live_violations = live_arm(source)
    print(f"  live arm ({LIVE}): {status}")
    for line in live_violations:
        print(f"    live-diff {line}")

    print("")
    if violations or live_violations:
        for line in violations + live_violations:
            print(f"  VIOLATION {line}")
        print(
            f"FAILED:r4_credential_rule_gate {len(violations) + len(live_violations)} "
            "violation(s) -- agent-self/config/AGENTS.md would deploy an INVERTED §9 over "
            "~/.claude. Owner action; this lane may only propose."
        )
        return 1
    print(
        "SUCCESS:r4_credential_rule_gate the deploy source carries the credential "
        f"non-negotiable and does not invert it (live arm: {status})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
