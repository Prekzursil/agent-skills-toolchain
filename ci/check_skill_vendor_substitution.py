#!/usr/bin/env python3
"""Detect vendor-substitution corruption in the repository skill trees.

WHY THIS EXISTS
---------------
A blind vendor rename previously changed Claude-specific names and paths into
plausible-looking Codex text.  Dual-write and inventory gates cannot detect the
defect when both trees carry the same bytes, and render gates only inspect YAML
shape.  This gate instead searches for measured, case-sensitive corruption
markers in every Markdown file below ``skills/`` and ``.agents/skills/``.

Fence or inline-code position is deliberately NOT used as a discriminator.
Measurement found three real corruptions inside fenced shell examples, while the
documentation teaching this trap contains legitimate mentions both inside and
outside fences.  Exemptions are therefore content-anchored:
``relative/path:marker:count``.  A pin that matches nothing is stale.  A pinned
file that shrinks below the count is stale.  A pinned file that grows past the
count is a new violation -- a new line in an exempted file is not pardoned.

Operational vendor-substitution corruptions in authored skill files
under the default roots were repaired.  Authored skill files are not
expected to stay RED.  Generated inventory is still scanned: a
``.Codex/`` hit in ``skills/SKILLS-MANIFEST.md`` is a finding, not a
detector defect, and is not exempted, so a default-root walk can still
exit RED on that generated file.  Operators can point ``--root`` at any
extra tree.

This gate identifies marker-shaped evidence, not every possible semantic vendor
error.  It never rewrites files and does not infer a repair or original pre-image.
Exit codes: 0 clean; 1 violations; 2 configuration error (fails closed).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROOTS = (Path(".agents/skills"), Path("skills"))
DEFAULT_EXEMPTIONS = Path("ci/skill-vendor-substitution-exemptions.txt")

MARKERS = (
    "Codex / Codex",
    "Codex + Codex",
    "by:Codex",
    "`Codex` | `codex`",
    "Codex-reflect",
    "current Codex model",
    ".Codex/",
    "Codex Workflow",
    "everything-Codex",
    "Everything Codex",
)

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_CONFIG = 2
RULE_VENDOR_SUBSTITUTION = "vendor-substitution"
RULE_STALE_EXEMPTION = "stale-exemption"


class ConfigurationError(ValueError):
    """The configured surface cannot support a trustworthy verdict."""


@dataclass(frozen=True)
class SkillFile:
    root: str
    relative_path: str
    display_path: str
    skill: str
    text: str


@dataclass(frozen=True)
class Exemption:
    relative_path: str
    marker: str
    expected_count: int
    reason: str


@dataclass(frozen=True)
class Violation:
    rule: str
    skill: str
    root: str
    path: str
    line: int
    marker: str
    detail: str


@dataclass(frozen=True)
class Report:
    files: int
    skills: int
    violations: tuple[Violation, ...]


def collect(roots: list[Path]) -> list[SkillFile]:
    """Read every Markdown file under existing roots; reject an empty walk."""
    found: list[SkillFile] = []
    existing = 0
    for root in roots:
        if not root.is_dir():
            continue
        existing += 1
        for path in sorted(root.rglob("*.md")):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise ConfigurationError(f"cannot read {path}: {exc}") from exc
            relative = path.relative_to(root).as_posix()
            parts = Path(relative).parts
            skill = parts[0] if len(parts) > 1 else "<root>"
            found.append(
                SkillFile(root.as_posix(), relative, path.as_posix(), skill, text)
            )
    if existing == 0:
        raise ConfigurationError(
            f"none of the skill roots exist: {[root.as_posix() for root in roots]}"
        )
    if not found:
        raise ConfigurationError(
            "walked the skill roots and found no Markdown files; refusing a clean "
            "verdict from an empty walk"
        )
    return found


def load_exemptions(path: Path | None) -> list[Exemption]:
    """Load ``relative/path:marker:count # reason`` entries without case folding."""
    if path is None:
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigurationError(f"cannot read exemptions file {path}: {exc}") from exc
    exemptions: list[Exemption] = []
    seen: set[tuple[str, str]] = set()
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entry, separator, reason = line.partition(" # ")
        head, count_colon, count_text = entry.rpartition(":")
        relative_path, marker_colon, marker = head.partition(":")
        try:
            expected_count = int(count_text)
        except ValueError:
            expected_count = -1
        if (
            not separator
            or not reason
            or not count_colon
            or not marker_colon
            or not relative_path
            or not marker
            or expected_count < 1
        ):
            raise ConfigurationError(
                f"malformed exemption at {path}:{number}; expected "
                "relative/path:marker:count # reason"
            )
        if marker not in MARKERS:
            raise ConfigurationError(
                f"unknown marker in exemption at {path}:{number}: {marker!r}"
            )
        if re.search(r"(^|/)\.\.?($|/)", relative_path) or "\\" in relative_path:
            raise ConfigurationError(
                f"non-canonical relative path in exemption at {path}:{number}: "
                f"{relative_path!r}"
            )
        key = (relative_path, marker)
        if key in seen:
            raise ConfigurationError(f"duplicate exemption at {path}:{number}: {entry}")
        seen.add(key)
        exemptions.append(Exemption(relative_path, marker, expected_count, reason))
    return exemptions


def evaluate(files: list[SkillFile], exemptions: list[Exemption]) -> Report:
    """Return violations; pins are per-file and fail closed on shrink or growth."""
    exempt_by_key = {(item.relative_path, item.marker): item for item in exemptions}
    matched_exemptions: set[tuple[str, str]] = set()
    short_pins: list[str] = []
    violations: list[Violation] = []
    for entry in files:
        lines = entry.text.splitlines()
        for marker in MARKERS:
            hits = [number for number, line in enumerate(lines, 1) if marker in line]
            key = (entry.relative_path, marker)
            pinned = exempt_by_key.get(key)
            if pinned is None:
                for line_number in hits:
                    violations.append(
                        Violation(
                            RULE_VENDOR_SUBSTITUTION,
                            entry.skill,
                            entry.root,
                            entry.display_path,
                            line_number,
                            marker,
                            f"{entry.relative_path}:{line_number} contains {marker!r}",
                        )
                    )
                continue
            observed = len(hits)
            if observed:
                matched_exemptions.add(key)
            if observed > pinned.expected_count:
                for line_number in hits[pinned.expected_count :]:
                    violations.append(
                        Violation(
                            RULE_VENDOR_SUBSTITUTION,
                            entry.skill,
                            entry.root,
                            entry.display_path,
                            line_number,
                            marker,
                            (
                                f"{entry.relative_path}:{line_number} contains "
                                f"{marker!r} (observed {observed} > pinned "
                                f"{pinned.expected_count})"
                            ),
                        )
                    )
            elif observed < pinned.expected_count:
                short_pins.append(
                    f"{entry.display_path}:{marker} observed {observed} < "
                    f"pinned {pinned.expected_count}"
                )
    stale = set(exempt_by_key) - matched_exemptions
    if stale or short_pins:
        parts: list[str] = []
        if stale:
            rendered = ", ".join(f"{path}:{marker}" for path, marker in sorted(stale))
            parts.append(f"configured path/marker matches nothing: {rendered}")
        if short_pins:
            parts.append("pinned count exceeds observed: " + ", ".join(short_pins))
        raise ConfigurationError(f"{RULE_STALE_EXEMPTION}: {'; '.join(parts)}")
    skills = len({(entry.root, entry.skill) for entry in files})
    return Report(len(files), skills, tuple(violations))


def _as_dict(item: Violation) -> dict[str, object]:
    return {
        "rule": item.rule,
        "skill": item.skill,
        "root": item.root,
        "path": item.path,
        "line": item.line,
        "marker": item.marker,
        "detail": item.detail,
    }


def render(report: Report) -> str:
    lines: list[str] = []
    for item in report.violations:
        lines.append(
            f"FAILED:skill-vendor-substitution {item.rule} {item.skill} "
            f"[{item.root}] -- {item.detail}"
        )
    if report.violations:
        lines.append(f"scanned {report.files} files across {report.skills} skills")
        lines.append(
            f"FAILED:skill-vendor-substitution violations={len(report.violations)}"
        )
    else:
        lines.append(
            f"SUCCESS:skill-vendor-substitution scanned {report.files} files "
            f"across {report.skills} skills"
        )
    return "\n".join(lines)


def run(
    roots: list[Path], exemptions_path: Path | None
) -> tuple[int, Report | None, str]:
    """Execute collection and evaluation so CLI and self-test share one path."""
    try:
        files = collect(roots)
        exemptions = load_exemptions(exemptions_path)
        report = evaluate(files, exemptions)
    except ConfigurationError as exc:
        return EXIT_CONFIG, None, str(exc)
    code = EXIT_VIOLATION if report.violations else EXIT_OK
    return code, report, ""


def self_test() -> int:
    """Execute RED, GREEN, empty-walk CLOSED, and exemption-growth RED controls."""
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        bad = base / "bad" / "fixture"
        clean = base / "clean" / "fixture"
        empty = base / "empty"
        taught = base / "taught" / "writing-skills"
        bad.mkdir(parents=True)
        clean.mkdir(parents=True)
        empty.mkdir()
        taught.mkdir(parents=True)
        (bad / "SKILL.md").write_text(
            "# bad\nRegister for Codex / Codex / Cursor\n",
            encoding="utf-8",
            newline="\n",
        )
        (clean / "SKILL.md").write_text(
            "# clean\nClaude Code / Codex / Cursor\n"
            "everything-claude-code\n~/.claude/\n",
            encoding="utf-8",
            newline="\n",
        )
        teaching = "# teach\nCodex / Codex once\n"
        (taught / "SKILL.md").write_text(teaching, encoding="utf-8", newline="\n")
        exemptions = base / "exemptions.txt"
        exemptions.write_text(
            "writing-skills/SKILL.md:Codex / Codex:1 # synthetic teaching pin\n",
            encoding="utf-8",
            newline="\n",
        )
        bad_code, bad_report, bad_error = run([base / "bad"], None)
        if (
            bad_code != EXIT_VIOLATION
            or bad_report is None
            or not bad_report.violations
        ):
            print(
                "FAILED:skill-vendor-substitution-self-test bad fixture did not go red: "
                f"exit={bad_code} error={bad_error}"
            )
            return EXIT_VIOLATION
        clean_code, clean_report, clean_error = run([base / "clean"], None)
        if clean_code != EXIT_OK or clean_report is None or clean_report.violations:
            print(
                "FAILED:skill-vendor-substitution-self-test clean fixture did not go green: "
                f"exit={clean_code} error={clean_error}"
            )
            return EXIT_VIOLATION
        empty_code, _, empty_error = run([empty], None)
        if empty_code != EXIT_CONFIG:
            print(
                "FAILED:skill-vendor-substitution-self-test empty root did not close: "
                f"exit={empty_code} error={empty_error}"
            )
            return EXIT_VIOLATION
        pinned_code, pinned_report, pinned_error = run([base / "taught"], exemptions)
        if pinned_code != EXIT_OK or pinned_report is None or pinned_report.violations:
            print(
                "FAILED:skill-vendor-substitution-self-test pinned teaching did not "
                f"stay green: exit={pinned_code} error={pinned_error}"
            )
            return EXIT_VIOLATION
        (taught / "SKILL.md").write_text(
            teaching + "Register as an MCP server (Codex / Codex / Cursor):\n",
            encoding="utf-8",
            newline="\n",
        )
        grown_code, grown_report, grown_error = run([base / "taught"], exemptions)
        if (
            grown_code != EXIT_VIOLATION
            or grown_report is None
            or not grown_report.violations
        ):
            print(
                "FAILED:skill-vendor-substitution-self-test grown exemption did not "
                f"go red: exit={grown_code} error={grown_error}"
            )
            return EXIT_VIOLATION
    print(
        "SUCCESS:skill-vendor-substitution-self-test red on bad, green on clean, "
        "closed on empty, red on exemption growth"
    )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        default=None,
        help="skill root to walk (repeatable); defaults to both repo skill roots",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable output"
    )
    parser.add_argument(
        "--self-test", action="store_true", help="run both-states controls"
    )
    parser.add_argument(
        "--exemptions",
        default=None,
        help=(
            "path to path/marker/count exemptions; defaults to the repo file only "
            "when using the default roots"
        ),
    )
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    roots = [Path(root) for root in args.roots] if args.roots else list(DEFAULT_ROOTS)
    exemptions_path = (
        Path(args.exemptions)
        if args.exemptions
        else (DEFAULT_EXEMPTIONS if args.roots is None else None)
    )
    code, report, error = run(roots, exemptions_path)
    if report is None:
        if args.json:
            print(
                json.dumps({"status": "configuration-error", "error": error}, indent=2)
            )
        print(
            f"FAILED:skill-vendor-substitution configuration <configuration> "
            f"[roots] -- {error}",
            file=sys.stdout,
        )
        return code
    if args.json:
        print(
            json.dumps(
                {
                    "files": report.files,
                    "skills": report.skills,
                    "violations": [_as_dict(item) for item in report.violations],
                },
                indent=2,
            )
        )
    else:
        print(render(report))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
