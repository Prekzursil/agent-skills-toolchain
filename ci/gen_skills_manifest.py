#!/usr/bin/env python3
"""Generate and verify ``skills/SKILLS-MANIFEST.md`` so the advertised inventory is complete.

WHY THIS EXISTS
---------------
``skills/SKILLS-MANIFEST.md`` describes itself as the auto-generated skill inventory for
this repository, but nothing generated it and nothing checked it. Measured on the commit
that added this script: 337 tracked ``skills/<name>/SKILL.md`` directories against 159
strictly parseable manifest rows, i.e. 178 real skills that an exact lookup in the
advertised inventory reports as ABSENT. ``recall-workflow-agent``, ``run-agent-monitor``
and ``workflow-monitor`` are three of them. A manifest-driven inventory, audit or
discovery step therefore silently omits a real repository skill -- a false negative, not a
stale count.

RELATIONSHIP TO ``ci/gen_skill_index.py`` -- THEY ARE NOT THE SAME CHECK
-----------------------------------------------------------------------
``gen_skill_index.py`` regenerates the PUBLICATION surface: the explicit component routes
in ``.claude-plugin/marketplace.json``, canonical-first from ``.agents/skills``. This
script regenerates the HUMAN inventory document under ``skills/``. A skill can be
published and still be missing from the prose manifest, which is exactly the observed
state, so the existing gate does not cover this one.

WHAT ``--check`` ENFORCES, AND WHAT IT DELIBERATELY DOES NOT
------------------------------------------------------------
``--check`` asserts the committed file is byte-identical to what ``--write`` produces:
one row per tracked skill directory, rows sorted by name, every table line a well-formed
three-cell row. It does NOT compare a row's description against the skill's frontmatter.
Descriptions and the ``Origin`` column are CURATED -- ``Origin`` has no tracked source of
truth anywhere in the repo (``skills/DEPLOYED-MANIFEST.json`` uses a different, partial
taxonomy) -- so a content check would either fire on all 159 curated rows immediately or
force the generator to invent provenance. Seeding a new row and then leaving it alone is
the honest contract; coverage is the property the defect is about.

ZERO IMPLICIT REMOVALS
----------------------
A row whose skill directory no longer exists is REPORTED but never deleted by ``--write``,
matching the union-before-overwrite rule ``gen_skill_index.py`` follows for declared-only
compatibility names. Retiring a name stays an explicit human edit. There are no orphan
rows today, so this does not weaken the current gate.

SCOPE, STATED SO IT IS NOT MISREAD AS COMPLETE COVERAGE OF EVERY ROOT
---------------------------------------------------------------------
The root is ``skills/`` -- the document lives there and that is the inventory rule the
audit used (``scripts/sync-skills.ps1``: a directory counts when it holds a ``SKILL.md``).
Measured on the same commit: 12 names exist under the canonical ``.agents/skills`` root
and not under ``skills/`` (``claim-verify-gate``, ``microsoft-foundry``, ``qdx-rush`` and
the nine superseded ``codex-*`` per-mode wrappers), and ``skills-claude-only/`` holds 35
more. Those remain outside this document by design; the published union of all three roots
is already gated by ``gen_skill_index.py``. Settling experiment for widening it: change
this root list and re-run both gates -- the open question is editorial (does a document in
``skills/`` inventory other roots), not mechanical.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from typing import NamedTuple

SKILLS_ROOT = "skills"
MANIFEST_RELPATH = "skills/SKILLS-MANIFEST.md"
UNCLASSIFIED_ORIGIN = "unclassified"
MAX_SEEDED_DESCRIPTION = 240
BLOCK_SCALAR_INDICATORS = {">", ">-", ">+", "|", "|-", "|+"}

TABLE_HEADER = "| Skill Name | Origin | Description |"
TABLE_RULE = "|---|---|---|"

DOC_HEADER = """# Skills Manifest

> Auto-generated skill inventory for the agent-skills-toolchain repository.
> Every directory under `skills/` holding a `SKILL.md` has exactly one row below,
> so an exact lookup here cannot report a tracked skill as absent.
>
> Regenerate: `python ci/gen_skills_manifest.py --write`
> Verify (CI): `python ci/gen_skills_manifest.py --check`
>
> Scope: the `skills/` projection only. Names that exist solely under the canonical
> `.agents/skills/` root, or under `skills-claude-only/`, are inventoried by
> `.claude-plugin/marketplace.json` (gated by `ci/gen_skill_index.py`), not here.
>
> `Origin` is curated provenance with no tracked source of truth, so rows the
> generator adds carry `unclassified` until a human classifies them. Descriptions
> are curated too: a new row is seeded from the skill's `description:` frontmatter
> and an existing row is never rewritten.
"""


class Row(NamedTuple):
    """One manifest table row."""

    name: str
    origin: str
    description: str


def enumerate_skill_dirs(
    repo: pathlib.Path, root: str = SKILLS_ROOT
) -> dict[str, pathlib.Path]:
    """Map skill name -> its ``SKILL.md``, identified by that file, never by a bare listing.

    Mirrors the inventory rule in ``scripts/sync-skills.ps1`` (a directory counts as a
    skill when it contains a ``SKILL.md``) and the enumeration style of
    ``ci/gen_skill_index.py`` (never ``ls | wc -l``, which counts symlinks and loose files).
    """
    base = repo / root
    if not base.is_dir():
        return {}
    return {
        path.parent.name: path
        for path in sorted(base.glob("*/SKILL.md"))
        if path.is_file()
    }


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def frontmatter_description(skill_md: pathlib.Path) -> str:
    """Read the ``description:`` value out of a SKILL.md YAML frontmatter block.

    Handles the three shapes present in this tree: a plain inline scalar, a quoted
    inline scalar, and a folded/literal block scalar (``>-`` and friends) whose text
    continues on the following more-indented lines. Six skills use the block form; a
    naive same-line regex returns ``>-`` for those, which is why this is not one regex.
    """
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else text[3:]
    lines = block.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^(\s*)description:\s*(.*)$", line)
        if not match:
            continue
        indent, inline = match.group(1), match.group(2).strip()
        if inline and inline not in BLOCK_SCALAR_INDICATORS:
            return _normalise(_strip_quotes(inline))
        collected: list[str] = []
        for follower in lines[index + 1 :]:
            if not follower.strip():
                collected.append("")
                continue
            leading = len(follower) - len(follower.lstrip())
            if leading <= len(indent):
                break
            collected.append(follower.strip())
        return _normalise(" ".join(collected))
    return ""


def _normalise(value: str) -> str:
    """Collapse whitespace so a folded scalar and an inline scalar render identically."""
    return re.sub(r"\s+", " ", value).strip()


def cell_escape(value: str) -> str:
    """Escape pipes so a description can never shift the column count.

    The committed ``ci-silent-pass-lint`` row carries raw ``|`` characters and parses as
    five cells instead of three -- the malformation this closes.
    """
    return value.replace("|", r"\|")


def cell_unescape(value: str) -> str:
    return value.replace(r"\|", "|")


def truncate(value: str, limit: int = MAX_SEEDED_DESCRIPTION) -> str:
    """Clip a seeded description on a word boundary; deterministic so ``--check`` is stable."""
    if len(value) <= limit:
        return value
    clipped = value[: limit - 3]
    space = clipped.rfind(" ")
    if space > 0:
        clipped = clipped[:space]
    return clipped.rstrip(" ,;:-") + "..."


def parse_manifest(text: str) -> tuple[list[Row], list[str]]:
    """Return (rows, malformed table lines) from a manifest document.

    A row with MORE than three cells is repaired rather than dropped: the surplus cells
    are re-joined into the description, which is what an unescaped pipe produced.
    """
    rows: list[Row] = []
    malformed: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        body = stripped[1:]
        if body.endswith("|") and not body.endswith(r"\|"):
            body = body[:-1]
        # Split on UNESCAPED pipes only: a description legitimately containing `\|`
        # must not re-shift the column count on the next round-trip.
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", body)]
        if len(cells) < 3:
            malformed.append(stripped)
            continue
        name = cells[0]
        if name == "Skill Name" or set(name) <= {"-"}:
            continue
        if len(cells) > 3:
            malformed.append(stripped)
        rows.append(Row(name, cells[1], cell_unescape(" | ".join(cells[2:])).strip()))
    return rows, malformed


def render(rows: list[Row]) -> str:
    lines = [DOC_HEADER, TABLE_HEADER, TABLE_RULE]
    for row in sorted(rows, key=lambda item: item.name):
        lines.append(f"| {row.name} | {row.origin} | {cell_escape(row.description)} |")
    return "\n".join(lines) + "\n"


class Sync(NamedTuple):
    rows: list[Row]
    added: list[str]
    orphans: list[str]
    malformed: list[str]


def sync(repo: pathlib.Path) -> Sync:
    manifest = repo / MANIFEST_RELPATH
    text = manifest.read_text(encoding="utf-8") if manifest.is_file() else ""
    rows, malformed = parse_manifest(text)
    known = {row.name: row for row in rows}
    skills = enumerate_skill_dirs(repo)
    added = sorted(name for name in skills if name not in known)
    for name in added:
        seed = truncate(frontmatter_description(skills[name]))
        known[name] = Row(name, UNCLASSIFIED_ORIGIN, seed)
    orphans = sorted(name for name in known if name not in skills)
    return Sync(list(known.values()), added, orphans, malformed)


def _summary(result: Sync, repo: pathlib.Path) -> str:
    return (
        f"skills_tracked={len(enumerate_skill_dirs(repo))} "
        f"manifest_rows={len(result.rows)} "
        f"added={len(result.added)} "
        f"orphan_rows={len(result.orphans)} "
        f"malformed_lines={len(result.malformed)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".", help="repository root (default: cwd)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check", action="store_true", help="fail if the manifest is stale"
    )
    mode.add_argument(
        "--write", action="store_true", help="rewrite the manifest in place"
    )
    args = parser.parse_args(argv)

    repo = pathlib.Path(args.repo).resolve()
    manifest = repo / MANIFEST_RELPATH
    result = sync(repo)
    expected = render(result.rows)

    if args.write:
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(expected, encoding="utf-8", newline="\n")
        print(f"wrote {MANIFEST_RELPATH}: {_summary(result, repo)}")
        if result.orphans:
            print(
                f"kept orphan rows (explicit removal only): {', '.join(result.orphans)}"
            )
        return 0

    current = manifest.read_text(encoding="utf-8") if manifest.is_file() else ""
    if current == expected:
        print(f"OK {MANIFEST_RELPATH}: {_summary(result, repo)}")
        if result.orphans:
            print(f"orphan rows present: {', '.join(result.orphans)}")
        return 0

    print(f"DRIFT {MANIFEST_RELPATH}: {_summary(result, repo)}", file=sys.stderr)
    if result.added:
        shown = ", ".join(result.added[:20])
        more = "" if len(result.added) <= 20 else f", +{len(result.added) - 20} more"
        print(f"missing rows: {shown}{more}", file=sys.stderr)
    if result.malformed:
        print(f"malformed table lines: {len(result.malformed)}", file=sys.stderr)
    print("run: python ci/gen_skills_manifest.py --write", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
