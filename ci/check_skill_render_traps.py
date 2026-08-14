#!/usr/bin/env python3
"""Gate the two RENDER-PATH traps that silently hide a skill's description.

WHY THIS EXISTS
---------------
A skill's ``description`` is its entire lexical recall surface.  The SKILLS2 lane
diagnosed two ways a description can be present on disk and still be *absent from
the listing the model receives* -- and both had actually shipped in this repo:

  R1 ``comment-truncation`` -- ``bc-drive-plus`` authored 793 characters in a PLAIN
     (unquoted) YAML scalar containing one `` #``.  ``#`` preceded by whitespace
     opens a YAML comment, so 440 characters were discarded and the entry rendered
     as a dangling ``...(closes bc-drive's``.  Fixed in ``ff14d2a6``.

  R2 ``block-scalar-in-invalid-frontmatter`` -- ``cv-studio`` wrote its description
     as a folded (``>``) block in a file whose frontmatter did not strict-parse (a
     ``: `` inside an unquoted ``license`` value -> ``ScannerError``).  The listing
     lost the description entirely and fell back to the body ``# H1``: 729 authored
     characters rendered as 74.  Fixed in ``878cd621``.

WHAT THE EXISTING GATES DO NOT COVER
------------------------------------
``ci/check_skill_description_ratchet.py`` is the closest neighbour and it is blind
to both.  Its ``parse_description()`` is a hand-rolled line reader: it never runs a
strict parse and never strips comments, so it measured bc-drive-plus at its
AUTHORED 793 and cv-studio at its AUTHORED 729 -- i.e. it charges the shared listing
budget for characters that were never rendered.  That is not a bug in the ratchet
(it is a shrink-only ratchet over authored text, by design); it is a different
surface.  This gate measures the RENDERED surface.  ``check_skill_dual_write.py``
compares the two roots to each other and would happily pass a defect present in
both.  ``check_skill_context_budget.py`` covers only the curated Codex tier.

WHY BOTH RULES BLOCK AND NEITHER HAS AN EXEMPTIONS FILE
--------------------------------------------------------
Measured 2026-08-14 over all 683 SKILL.md files in the two repo roots: **zero**
violations of either rule, so blocking is adoptable at HEAD without pinning any
debt.  Unlike the ratchet's over-length backlog there is no legitimate instance to
grandfather -- both rules describe a description the author wrote and the reader
never sees, and both fixes are one line (quote the scalar).  An exemptions file
here would only create a stale-pin surface to police.

WHAT THIS GATE DELIBERATELY DOES **NOT** CLAIM
-----------------------------------------------
A frontmatter that fails a strict parse is NOT by itself a render failure, and this
gate does not treat it as one.  That claim was shipped once in ``writing-skills``
and REFUTED: of the six live skills carrying a ``: `` in a plain ``description``
scalar, five render in full -- the client's parser is more forgiving than PyYAML.
Strict-invalid files are therefore reported ADVISORY and never block.  Only the
measured INTERSECTION (strict-invalid *and* a block scalar) is a violation.

Exit codes:  0 clean · 1 violations · 2 configuration error (fails CLOSED).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ROOTS = (Path(".agents/skills"), Path("skills"))

#: Keys charged against the client's per-entry listing budget.  Both are rendered,
#: so a trap in either one costs real recall surface.
DESCRIPTION_KEYS = ("description", "when_to_use")

#: YAML block-scalar indicators.  A block scalar is the shape that loses EVERYTHING
#: (rather than truncating) when the surrounding mapping does not parse.
BLOCK_TOKENS = frozenset({"|", ">", "|-", ">-", "|+", ">+"})

RULE_COMMENT_TRUNCATION = "comment-truncation"
RULE_BLOCK_IN_INVALID = "block-scalar-in-invalid-frontmatter"

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_CONFIG = 2

_FRONTMATTER_OPEN = "---"


class ConfigurationError(ValueError):
    """The surface could not be measured, so no verdict may be issued.

    Distinct from a violation on purpose: a gate that cannot read its inputs must
    exit non-zero rather than report a clean surface it never measured.
    """


@dataclass
class SkillFile:
    skill: str
    root: str
    path: Path
    frontmatter: str
    strict_ok: bool
    strict_error: str = ""
    #: key -> style in {"plain", "quoted", "block", "empty"}
    styles: dict[str, str] = field(default_factory=dict)
    #: key -> the raw plain text (value line plus indented continuations)
    plain_values: dict[str, str] = field(default_factory=dict)


def _strict_parse(frontmatter: str) -> tuple[bool, str]:
    """Strict-parse the frontmatter with PyYAML.

    A missing PyYAML is a CONFIGURATION error, never a pass: silently downgrading
    to "cannot check, therefore clean" is the exact no-op-gate shape this repo's
    ci-hygiene rule forbids.
    """
    try:
        import yaml  # noqa: PLC0415 - deliberately local; see docstring
    except ImportError as exc:  # pragma: no cover - exercised by the import guard test
        raise ConfigurationError(
            "PyYAML is required to strict-parse skill frontmatter; refusing to "
            "report a clean surface from a parser that is not installed"
        ) from exc
    try:
        loaded = yaml.safe_load(frontmatter)
    except Exception as exc:  # noqa: BLE001 - any loader failure is "strict-invalid"
        return False, type(exc).__name__
    if not isinstance(loaded, dict):
        return False, "not-a-mapping"
    return True, ""


def _split_frontmatter(path: Path) -> str:
    """Return the frontmatter body, or raise ConfigurationError.

    Universal-newline decoding is deliberate and matches the ratchet: a CRLF
    working tree and the LF stored blob must produce the SAME verdict, or the gate
    would disagree with itself between a local run and CI.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"cannot read {path}: {exc}") from exc
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_OPEN:
        raise ConfigurationError(f"no YAML frontmatter: {path}")
    for index, line in enumerate(lines[1:], 1):
        if line.strip() == _FRONTMATTER_OPEN:
            return "\n".join(lines[1:index])
    raise ConfigurationError(f"unclosed YAML frontmatter: {path}")


def _scan_keys(frontmatter: str) -> tuple[dict[str, str], dict[str, str]]:
    """Classify each description key's scalar STYLE and collect plain text.

    Style classification is lexical on purpose: the whole point is to reason about
    files a strict parser rejects, where ``yaml.safe_load`` returns nothing to
    inspect.  Only top-level keys (column 0) are considered.
    """
    styles: dict[str, str] = {}
    plain_values: dict[str, str] = {}
    lines = frontmatter.splitlines()
    for index, line in enumerate(lines):
        key, separator, raw = line.partition(":")
        # Only a top-level key counts.  ``partition`` keeps any leading whitespace in
        # ``key``, so an indented ``description:`` inside a block scalar fails the
        # membership test and is skipped -- which is what we want.
        if not separator or key not in DESCRIPTION_KEYS:
            continue
        if key in styles:  # a duplicate key: the first wins, as YAML readers vary
            continue
        value = raw.strip()
        if value in BLOCK_TOKENS:
            styles[key] = "block"
            continue
        if value == "":
            styles[key] = "empty"
            continue
        if value[0] in "\"'":
            styles[key] = "quoted"
            continue
        styles[key] = "plain"
        # A plain scalar may continue onto indented lines; the comment trap can sit
        # on any of them, so the whole logical scalar is collected.
        collected = [value]
        cursor = index + 1
        while (
            cursor < len(lines)
            and lines[cursor][:1].isspace()
            and lines[cursor].strip()
        ):
            collected.append(lines[cursor].strip())
            cursor += 1
        plain_values[key] = "\n".join(collected)
    return styles, plain_values


def load(path: Path, skill: str, root: str) -> SkillFile:
    frontmatter = _split_frontmatter(path)
    strict_ok, strict_error = _strict_parse(frontmatter)
    styles, plain_values = _scan_keys(frontmatter)
    return SkillFile(
        skill=skill,
        root=root,
        path=path,
        frontmatter=frontmatter,
        strict_ok=strict_ok,
        strict_error=strict_error,
        styles=styles,
        plain_values=plain_values,
    )


def collect(roots: list[Path]) -> list[SkillFile]:
    """Parse every SKILL.md under every root.  An empty walk is a config error."""
    found: list[SkillFile] = []
    seen_roots = 0
    for root in roots:
        if not root.is_dir():
            continue
        seen_roots += 1
        for path in sorted(root.glob("*/SKILL.md")):
            if path.is_file():
                found.append(load(path, path.parent.name, root.as_posix()))
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


def _comment_cut(value: str) -> int | None:
    """Index where a YAML comment opens inside a plain scalar, or None.

    ``#`` opens a comment only when it starts the scalar or follows whitespace;
    ``foo#bar`` is a literal ``#`` and must NOT fire.
    """
    match = re.search(r"(?:^|\s)#", value)
    return match.start() if match else None


def evaluate(
    files: list[SkillFile],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Return (violations, advisory).  Violations block; advisory never does."""
    violations: list[dict[str, object]] = []
    strict_invalid: list[str] = []

    for entry in files:
        if not entry.strict_ok:
            strict_invalid.append(f"{entry.root}/{entry.skill} [{entry.strict_error}]")

        for key in DESCRIPTION_KEYS:
            value = entry.plain_values.get(key)
            if value is None:
                continue
            cut = _comment_cut(value)
            if cut is None:
                continue
            kept = len(value[:cut].rstrip())
            violations.append(
                {
                    "rule": RULE_COMMENT_TRUNCATION,
                    "skill": entry.skill,
                    "root": entry.root,
                    "path": entry.path.as_posix(),
                    "detail": (
                        f"{key} is a plain scalar containing '#' after whitespace, which "
                        f"opens a YAML comment: {kept} of {len(value)} characters survive "
                        f"into the listing. Quote the scalar or drop the '#'."
                    ),
                }
            )

        if not entry.strict_ok and entry.styles.get("description") == "block":
            violations.append(
                {
                    "rule": RULE_BLOCK_IN_INVALID,
                    "skill": entry.skill,
                    "root": entry.root,
                    "path": entry.path.as_posix(),
                    "detail": (
                        f"description is a block scalar and the frontmatter does not "
                        f"strict-parse ({entry.strict_error}); measured on cv-studio, the "
                        f"listing then drops the description entirely and falls back to the "
                        f"body '# H1'. Quote the value that breaks the parse."
                    ),
                }
            )

    advisory = {
        "files_measured": len(files),
        "strict_invalid_count": len(strict_invalid),
        "strict_invalid": sorted(strict_invalid),
        "note": (
            "strict-invalid alone is ADVISORY: measured 5 of 6 such live skills still "
            "render in full, so the client's parser is more forgiving than PyYAML. "
            "Only the intersection with a block scalar blocks."
        ),
    }
    return violations, advisory


def render(violations: list[dict[str, object]], advisory: dict[str, object]) -> str:
    lines = [
        f"skill render-trap surface (ADVISORY): {advisory['files_measured']} SKILL.md "
        f"measured, {advisory['strict_invalid_count']} strict-invalid frontmatter"
    ]
    if not violations:
        lines.append("SUCCESS:skill-render-traps no violations")
        return "\n".join(lines)
    for violation in violations:
        lines.append(
            f"FAILED:skill-render-traps {violation['rule']} "
            f"{violation['skill']} [{violation['root']}] -- {violation['detail']}"
        )
    lines.append(f"FAILED:skill-render-traps violations={len(violations)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        default=None,
        help="skill root to walk (repeatable); defaults to the two repo roots",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable output"
    )
    args = parser.parse_args(argv)

    roots = [Path(r) for r in args.roots] if args.roots else list(DEFAULT_ROOTS)
    try:
        files = collect(roots)
        violations, advisory = evaluate(files)
    except ConfigurationError as exc:
        print(f"FAILED:skill-render-traps configuration -- {exc}", file=sys.stderr)
        return EXIT_CONFIG

    if args.json:
        print(json.dumps({"violations": violations, "advisory": advisory}, indent=2))
    else:
        print(render(violations, advisory))
    return EXIT_VIOLATION if violations else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
