#!/usr/bin/env python3
"""Shrink-only ratchet over the repo's skill DESCRIPTION surface.

WHY THIS EXISTS
---------------
A skill's ``description`` is the entire lexical recall surface for auto-selection.
The body is read on demand; the description is what decides whether the skill is
ever reached at all.  Measured 2026-08-12 in a live session: **26-30 curated
skills rendered with NO description**, so they could not be auto-picked even
though they were curated and their SKILL.md carried real text on disk (up to
1,750 chars).  The DOMINANT mechanism is client-side BUDGET TRUNCATION in
listing order, evidenced three independent ways (byte-stable skills flipping
between sessions; byte-identical descriptions rendering differently across
namespaces in one session; 12 folded scalars producing 0 bare and 11
over-1,024 descriptions producing 1 bare).

That sentence used to end "not a per-file parse failure", and the EXCLUSIVE half
was REFUTED -- kept here rather than deleted.  ``cv-studio`` wrote a folded
description in a frontmatter that does not strict-parse; the listing dropped the
description entirely and rendered 74 characters of the body ``# H1`` in place of
729, at a length nowhere near any cap.  Counting folded scalars cannot see that
class, because the defect is the INTERSECTION of a fold with an unparseable
frontmatter -- a fold in a VALID file renders fine (11 of 12 measured).  That
intersection is now gated separately by ``ci/check_skill_render_traps.py``, which
measures the RENDERED surface; this gate measures the AUTHORED one.

Consequence: **descriptions are a scarce shared resource.**  Every char one
skill spends is a char another skill cannot have.  Nothing in this repo charged
that.  ``ci/check_skill_context_budget.py`` enforces a real ceiling but only over
the curated DAILY tier (``ci/skills-allowlist``, 8,000 chars); the 337-346 skill
fleet under ``.agents/skills`` and ``skills`` was ungated.

WHAT THIS GATE DOES AND DELIBERATELY DOES NOT DO
------------------------------------------------
It is a RATCHET, not a ceiling.  An absolute ceiling would be RED at HEAD (5
descriptions already exceed the 1,024-char spec limit, 6 already use folded
scalars) and would red-block main and every sibling PR.  So the existing debt is
pinned in ``ci/skill-description-exemptions.txt`` and the gate refuses only:

    over-spec        a NEW description above 1,024 chars, or a pinned one that grew
    folded           a NEW folded/literal block-scalar or continuation description
    stale-exemption  a pinned skill that no longer violates -- delete its line
    unknown-exemption a pinned skill that exists in neither root
    parse            a SKILL.md whose name/description cannot be read (fail closed)

The exemption file can therefore only get SHORTER.  Fixing a skill without
deleting its line is itself a failure, which is what stops the list becoming a
permanent excuse.

WHAT IT REPORTS BUT NEVER BLOCKS ON
-----------------------------------
The cumulative description surface.  CI genuinely cannot pin the truncation
boundary: it is SESSION-DEPENDENT.  Two independent sessions fitted the same
fleet's boundary at ~108,144 and at 102,511-105,336 description chars -- a
13-skill shift -- and the bare-skill count moved 26 / 30 / 29 across three
samples.  Blocking on a number measured in one session would be the overclaim
this lane already had to retract once, so the total is printed as ADVISORY with
its own uncertainty stated inline.  Settling experiment for anyone who wants to
make it blocking: sample cumsum-to-first-bare across 3-4 sessions of differing
injected-context weight and check whether the boundary tracks total injected
context rather than the skill surface alone.

Exit codes:
    0  no violations
    1  violations found
    2  configuration error (including an empty walk -- fail closed, never
       "found nothing, therefore pass")

Usage:
    python ci/check_skill_description_ratchet.py
    python ci/check_skill_description_ratchet.py --json
    python ci/check_skill_description_ratchet.py --root <dir> --exemptions <file>
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: The Agent Skills spec ceiling for a single description.
SPEC_MAX_CHARS = 1024

#: YAML block-scalar indicators that make a description multi-line.
_FOLD_TOKENS = frozenset({"|", ">", "|-", ">-", "|+", ">+"})

DEFAULT_ROOTS = (Path(".agents/skills"), Path("skills"))
DEFAULT_EXEMPTIONS = Path("ci/skill-description-exemptions.txt")

RULE_OVER_SPEC = "over-spec"
RULE_FOLDED = "folded"

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_CONFIG = 2


class ConfigurationError(ValueError):
    """The surface could not be measured safely, so no verdict may be issued.

    Deliberately distinct from ``ci/check_skill_context_budget.py``'s
    ``ConfigurationError``: ``ci`` is not a package (its tests reach each module
    through a ``sys.path`` insert), so importing that symbol would put path
    surgery inside a CI gate for no behavioural gain.  Same repo precedent as
    ``platform/lib/wfdsl/authz_census.py``'s ``CensusError``.  The two gates also
    measure different surfaces -- that one the curated DAILY tier against an
    8,000-char ceiling, this one the whole fleet against a shrink-only ratchet.
    """


@dataclass(frozen=True)
class Description:
    """One skill's parsed frontmatter description and its shape."""

    skill: str
    root: str
    text: str
    folded: bool

    @property
    def chars(self) -> int:
        return len(self.text)


@dataclass
class Exemptions:
    """Pinned, shrink-only debt."""

    over_spec: dict[str, int] = field(default_factory=dict)
    folded: set[str] = field(default_factory=set)

    @property
    def names(self) -> set[str]:
        return set(self.over_spec) | set(self.folded)


def parse_exemptions(path: Path) -> Exemptions:
    """Read the pinned debt file, rejecting malformed or duplicated entries."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"cannot read exemptions {path}: {exc}") from exc

    out = Exemptions()
    for lineno, line in enumerate(raw.splitlines(), 1):
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        parts = entry.split(":")
        rule = parts[0]
        if rule == RULE_OVER_SPEC:
            if len(parts) != 3:
                raise ConfigurationError(
                    f"{path}:{lineno}: expected 'over-spec:<name>:<max>', got {entry!r}"
                )
            name = parts[1]
            try:
                pinned = int(parts[2])
            except ValueError as exc:
                raise ConfigurationError(
                    f"{path}:{lineno}: pinned max is not an integer: {entry!r}"
                ) from exc
            if pinned <= SPEC_MAX_CHARS:
                raise ConfigurationError(
                    f"{path}:{lineno}: pinned max {pinned} is not above the "
                    f"{SPEC_MAX_CHARS}-char spec limit, so the entry grants nothing"
                )
            if name in out.over_spec:
                raise ConfigurationError(f"{path}:{lineno}: duplicate entry {name!r}")
            out.over_spec[name] = pinned
        elif rule == RULE_FOLDED:
            if len(parts) != 2:
                raise ConfigurationError(
                    f"{path}:{lineno}: expected 'folded:<name>', got {entry!r}"
                )
            name = parts[1]
            if name in out.folded:
                raise ConfigurationError(f"{path}:{lineno}: duplicate entry {name!r}")
            out.folded.add(name)
        else:
            raise ConfigurationError(f"{path}:{lineno}: unknown rule {rule!r}")
    return out


def parse_description(path: Path, skill: str, root: str) -> Description:
    """Parse one SKILL.md's description, or fail closed.

    Universal-newline decoding is deliberate: CRLF in a Windows working tree and
    LF in the stored blob must measure the SAME length, or the gate would report
    a different verdict locally than in CI.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"cannot read {path}: {exc}") from exc

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ConfigurationError(f"no YAML frontmatter: {path}")
    end = None
    for index, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end = index
            break
    if end is None:
        raise ConfigurationError(f"unclosed YAML frontmatter: {path}")

    frontmatter = lines[1:end]
    description = ""
    folded = False
    found = False
    for index, line in enumerate(frontmatter):
        key, separator, value = line.partition(":")
        if not separator or key.strip() != "description":
            continue
        found = True
        value = value.strip()
        if value in _FOLD_TOKENS:
            folded = True
            collected: list[str] = []
            cursor = index + 1
            while cursor < len(frontmatter) and (
                frontmatter[cursor][:1].isspace() or not frontmatter[cursor].strip()
            ):
                collected.append(frontmatter[cursor].strip())
                cursor += 1
            description = " ".join(part for part in collected if part)
            break
        description = _unquote(value)
        if index + 1 < len(frontmatter) and frontmatter[index + 1][:1].isspace():
            folded = True
            cursor = index + 1
            while cursor < len(frontmatter) and frontmatter[cursor][:1].isspace():
                description += " " + frontmatter[cursor].strip()
                cursor += 1
        break

    if not found or not description:
        raise ConfigurationError(f"skill has no usable description: {path}")
    return Description(skill=skill, root=root, text=description, folded=folded)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def collect(roots: list[Path]) -> list[Description]:
    """Parse every SKILL.md under every root.  An empty walk is a config error."""
    found: list[Description] = []
    seen_roots = 0
    for root in roots:
        if not root.is_dir():
            continue
        seen_roots += 1
        for path in sorted(root.glob("*/SKILL.md")):
            if path.is_file():
                found.append(parse_description(path, path.parent.name, root.as_posix()))
    if seen_roots == 0:
        raise ConfigurationError(
            f"none of the skill roots exist: {[r.as_posix() for r in roots]}"
        )
    if not found:
        raise ConfigurationError(
            "walked the skill roots and found no SKILL.md; refusing to report a "
            "clean surface from an empty walk"
        )
    return found


def evaluate(
    descriptions: list[Description], exemptions: Exemptions
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Return (violations, advisory).  Violations block; advisory never does."""
    violations: list[dict[str, object]] = []
    by_name: dict[str, list[Description]] = {}
    for description in descriptions:
        by_name.setdefault(description.skill, []).append(description)

    for description in descriptions:
        name = description.skill
        if description.chars > SPEC_MAX_CHARS:
            pinned = exemptions.over_spec.get(name)
            if pinned is None:
                violations.append(
                    {
                        "rule": RULE_OVER_SPEC,
                        "skill": name,
                        "root": description.root,
                        "detail": (
                            f"description is {description.chars} chars, above the "
                            f"{SPEC_MAX_CHARS}-char spec limit, and is not pinned"
                        ),
                    }
                )
            elif description.chars > pinned:
                violations.append(
                    {
                        "rule": RULE_OVER_SPEC,
                        "skill": name,
                        "root": description.root,
                        "detail": (
                            f"description grew to {description.chars} chars, past its "
                            f"pinned ceiling of {pinned}"
                        ),
                    }
                )
        if description.folded and name not in exemptions.folded:
            violations.append(
                {
                    "rule": RULE_FOLDED,
                    "skill": name,
                    "root": description.root,
                    "detail": (
                        "description is a folded/literal block scalar or a "
                        "continuation line; make it one line"
                    ),
                }
            )

    # The ratchet half: a pinned entry that no longer earns its exemption.
    for name in sorted(exemptions.over_spec):
        present = by_name.get(name)
        if not present:
            violations.append(
                {
                    "rule": "unknown-exemption",
                    "skill": name,
                    "root": "-",
                    "detail": "pinned over-spec skill exists in no skill root",
                }
            )
        elif all(d.chars <= SPEC_MAX_CHARS for d in present):
            violations.append(
                {
                    "rule": "stale-exemption",
                    "skill": name,
                    "root": "-",
                    "detail": (
                        "description is now within the spec limit; delete its "
                        "over-spec line from the exemptions file"
                    ),
                }
            )
    for name in sorted(exemptions.folded):
        present = by_name.get(name)
        if not present:
            violations.append(
                {
                    "rule": "unknown-exemption",
                    "skill": name,
                    "root": "-",
                    "detail": "pinned folded skill exists in no skill root",
                }
            )
        elif not any(d.folded for d in present):
            violations.append(
                {
                    "rule": "stale-exemption",
                    "skill": name,
                    "root": "-",
                    "detail": (
                        "description is now one line; delete its folded line from "
                        "the exemptions file"
                    ),
                }
            )

    canonical = [d for d in descriptions if d.root.endswith(".agents/skills")]
    surface = canonical or descriptions
    advisory = {
        "root_measured": surface[0].root,
        "skills": len(surface),
        "description_chars": sum(d.chars for d in surface),
        "note": (
            "ADVISORY ONLY -- never blocks. The client truncation boundary is "
            "SESSION-DEPENDENT: two independent sessions fitted the same fleet at "
            "~108,144 and at 102,511-105,336 description chars (a 13-skill shift), "
            "and the bare-skill count moved 26/29/30 across three samples. A "
            "blocking threshold here would be a one-session number generalised to "
            "a fleet constant."
        ),
    }
    return violations, advisory


def render(violations: list[dict[str, object]], advisory: dict[str, object]) -> str:
    lines = [
        f"skill description surface (ADVISORY): {advisory['description_chars']} chars "
        f"across {advisory['skills']} skills in {advisory['root_measured']}",
        f"  {advisory['note']}",
        "",
    ]
    if not violations:
        lines.append("SUCCESS:skill-description-ratchet no violations")
        return "\n".join(lines)
    for violation in violations:
        lines.append(
            f"FAILED:skill-description-ratchet {violation['rule']} "
            f"{violation['skill']} [{violation['root']}] -- {violation['detail']}"
        )
    lines.append(
        f"FAILED:skill-description-ratchet violations={len(violations)}",
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="skill description ratchet")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument(
        "--root",
        type=Path,
        action="append",
        dest="roots",
        help="skill root to check (repeatable); defaults to both repo roots",
    )
    parser.add_argument("--exemptions", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    namespace = parser.parse_args(argv)

    repo = namespace.repo.resolve()
    roots = [
        root if root.is_absolute() else repo / root
        for root in (namespace.roots or list(DEFAULT_ROOTS))
    ]
    exemptions_path = namespace.exemptions or (repo / DEFAULT_EXEMPTIONS)
    if not exemptions_path.is_absolute():
        exemptions_path = repo / exemptions_path

    try:
        exemptions = parse_exemptions(exemptions_path)
        descriptions = collect(roots)
    except ConfigurationError as exc:
        print(f"CONFIGURATION ERROR: {exc}", file=sys.stderr)
        return EXIT_CONFIG

    violations, advisory = evaluate(descriptions, exemptions)
    if namespace.json:
        print(json.dumps({"violations": violations, "advisory": advisory}, indent=2))
    else:
        print(render(violations, advisory))
    return EXIT_VIOLATION if violations else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
