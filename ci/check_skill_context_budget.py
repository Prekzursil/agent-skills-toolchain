#!/usr/bin/env python3
"""Validate the curated Codex skill tier before it is installed.

The runner has an 8,000-character skill-description ceiling. Only each skill's
frontmatter ``name`` and ``description`` are session-start tax; its body is read
on demand. This checker measures the installed provider projection, also charges
the authoritative trigger surface so a stale overlay cannot hide source growth,
and reports the untouched canonical/projection union as library inventory.

This is intentionally read-only. It never copies, rewrites, or removes a skill.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

CANONICAL_ROOT = Path(".agents/skills")
PROJECTION_ROOTS = (Path("skills"), Path("skills-claude-only"))
DEFAULT_ALLOWLIST = Path("ci/codex-skill-allowlist.txt")
DEFAULT_RUNTIME_ROOT = Path("ci/skills-allowlist")
DEFAULT_MAX_TRIGGER_CHARS = 8_000
CONTROL_SKILL = "agent-sort"

_NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]*\Z")


class ConfigurationError(ValueError):
    """The tier cannot be measured safely."""


class BudgetExceeded(ValueError):
    """The measured trigger surface exceeds its declared ceiling."""


@dataclass(frozen=True)
class SkillMetadata:
    """The two load phases of one installed SKILL.md."""

    name: str
    description: str
    body_chars: int

    @property
    def trigger_text(self) -> str:
        return f"{self.name}: {self.description}\n"


@dataclass(frozen=True)
class BudgetReport:
    """Measured DAILY trigger tax and retained catalog size."""

    daily_count: int
    library_count: int
    catalog_count: int
    runtime_trigger_chars: int
    canonical_trigger_chars: int
    body_chars: int

    @property
    def trigger_chars(self) -> int:
        """Conservative charge: source growth cannot hide behind an old overlay."""
        return max(self.runtime_trigger_chars, self.canonical_trigger_chars)


def _under(repo: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo / path


def _skill_paths(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    return {
        path.parent.name: path for path in root.glob("*/SKILL.md") if path.is_file()
    }


def build_catalog(repo: Path) -> dict[str, Path]:
    """Union projection-only skills, then overwrite with D-001 authority."""
    canonical = _skill_paths(repo / CANONICAL_ROOT)
    if CONTROL_SKILL not in canonical:
        raise ConfigurationError(
            f"detector control {CONTROL_SKILL!r} was not found under "
            f"{repo / CANONICAL_ROOT}; refusing an unvalidated census"
        )
    catalog: dict[str, Path] = {}
    for root in PROJECTION_ROOTS:
        catalog.update(_skill_paths(repo / root))
    catalog.update(canonical)
    return catalog


def read_allowlist(path: Path) -> tuple[str, ...]:
    """Read unique lower-case skill directory names, tolerating CRLF and comments."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigurationError(f"cannot read allowlist {path}: {exc}") from exc

    names: list[str] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(lines, 1):
        name = raw.strip()
        if not name or name.startswith("#"):
            continue
        if _NAME_RE.fullmatch(name) is None:
            raise ConfigurationError(
                f"invalid skill name at {path}:{line_number}: {name!r}"
            )
        if name in seen:
            raise ConfigurationError(
                f"duplicate skill name at {path}:{line_number}: {name!r}"
            )
        seen.add(name)
        names.append(name)
    if not names:
        raise ConfigurationError(f"allowlist {path} contains no skill names")
    return tuple(names)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_skill(path: Path) -> SkillMetadata:
    """Parse the one-line name/description fields and count the on-demand body."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"cannot read skill {path}: {exc}") from exc
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ConfigurationError(f"skill has no YAML frontmatter: {path}")
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as exc:
        raise ConfigurationError(
            f"skill has unclosed YAML frontmatter: {path}"
        ) from exc

    name = ""
    description = ""
    frontmatter = lines[1:end]
    for index, line in enumerate(frontmatter):
        key, separator, value = line.partition(":")
        if not separator or key not in {"name", "description"}:
            continue
        value = value.strip()
        if key == "name":
            name = _unquote(value)
            continue
        if value in {"|", ">", "|-", ">-", "|+", ">+"}:
            raise ConfigurationError(
                f"skill description must be one line for deterministic budgeting: {path}"
            )
        if index + 1 < len(frontmatter) and frontmatter[index + 1][:1].isspace():
            raise ConfigurationError(
                f"skill description must be one line for deterministic budgeting: {path}"
            )
        description = _unquote(value)

    if not name or not description:
        raise ConfigurationError(
            f"skill needs one-line name and description fields: {path}"
        )
    return SkillMetadata(
        name=name,
        description=description,
        body_chars=len("".join(lines[end + 1 :])),
    )


def analyze(repo: Path, allowlist: Path, runtime_root: Path) -> BudgetReport:
    """Measure the installed DAILY tier without charging on-demand bodies."""
    repo = repo.resolve()
    allowlist = _under(repo, allowlist)
    runtime_root = _under(repo, runtime_root)
    daily_names = read_allowlist(allowlist)
    daily = set(daily_names)
    catalog = build_catalog(repo)
    canonical = _skill_paths(repo / CANONICAL_ROOT)

    noncanonical = sorted(daily - set(canonical))
    if noncanonical:
        raise ConfigurationError(
            "DAILY skills are absent from the authoritative .agents/skills root: "
            + ", ".join(noncanonical)
        )

    runtime = _skill_paths(runtime_root)
    missing = sorted(daily - set(runtime))
    extra = sorted(set(runtime) - daily)
    if missing or extra:
        raise ConfigurationError(
            "runtime tier does not match allowlist; "
            f"missing={missing or 'none'}, extra={extra or 'none'}"
        )

    runtime_trigger_chars = 0
    canonical_trigger_chars = 0
    body_chars = 0
    for expected_name in daily_names:
        runtime_metadata = parse_skill(runtime[expected_name])
        canonical_metadata = parse_skill(canonical[expected_name])
        if runtime_metadata.name != expected_name:
            raise ConfigurationError(
                f"runtime frontmatter name {runtime_metadata.name!r} does not match "
                f"directory {expected_name!r}"
            )
        if canonical_metadata.name != expected_name:
            raise ConfigurationError(
                f"canonical frontmatter name {canonical_metadata.name!r} does not match "
                f"directory {expected_name!r}"
            )
        runtime_trigger_chars += len(runtime_metadata.trigger_text)
        canonical_trigger_chars += len(canonical_metadata.trigger_text)
        body_chars += runtime_metadata.body_chars

    return BudgetReport(
        daily_count=len(daily),
        library_count=len(set(catalog) - daily),
        catalog_count=len(catalog),
        runtime_trigger_chars=runtime_trigger_chars,
        canonical_trigger_chars=canonical_trigger_chars,
        body_chars=body_chars,
    )


def check(report: BudgetReport, max_trigger_chars: int) -> None:
    """Raise when the measured DAILY trigger surface exceeds the explicit cap."""
    if max_trigger_chars <= 0:
        raise ConfigurationError("max trigger chars must be positive")
    if report.trigger_chars > max_trigger_chars:
        raise BudgetExceeded(
            f"DAILY trigger surface {report.trigger_chars} chars exceeds "
            f"the {max_trigger_chars}-char budget"
        )


def render(report: BudgetReport, max_trigger_chars: int) -> str:
    """Render the two costs without presenting body size as session tax."""
    return "\n".join(
        (
            "skill context budget: "
            f"{report.trigger_chars}/{max_trigger_chars} trigger chars "
            f"(runtime {report.runtime_trigger_chars}; "
            f"canonical {report.canonical_trigger_chars})",
            f"DAILY: {report.daily_count} | LIBRARY retained in catalog: "
            f"{report.library_count} | catalog: {report.catalog_count}",
            f"on-demand skill bodies (not charged above): {report.body_chars} chars",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    parser.add_argument(
        "--max-trigger-chars", type=int, default=DEFAULT_MAX_TRIGGER_CHARS
    )
    args = parser.parse_args(argv)

    try:
        report = analyze(args.repo, args.allowlist, args.runtime_root)
        check(report, args.max_trigger_chars)
    except ConfigurationError as exc:
        print(f"CONFIGURATION ERROR: {exc}", file=sys.stderr)
        return 2
    except BudgetExceeded as exc:
        print(f"OVER BUDGET: {exc}", file=sys.stderr)
        return 1
    print(render(report, args.max_trigger_chars))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
