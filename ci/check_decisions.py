#!/usr/bin/env python3
"""Decision-record gate for docs/decisions/ (RUNBOOK-2026-09-24-settle-and-harden, 4a).

Checks every docs/decisions/*.md except README.md and TEMPLATE.md. Exits 1 with one line
per problem when frontmatter is missing or malformed, when an `accepted` record is past
`review_by` with no `retested:` dated on or after it, or when `supersedes` names a
missing file; otherwise prints a one-line summary and exits 0. Exits 2 when the
directory itself is missing, so a check with nothing to read never reports clean.
The frontmatter is a YAML subset parsed with the stdlib (`key: value` lines, `- item`
lists under a key, `#` comments); paths in it are repo-relative.

    python ci/check_decisions.py [--today YYYY-MM-DD] [--root REPO]
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DECISIONS = Path("docs", "decisions")
SKIP = {"README.md", "TEMPLATE.md"}
STATUSES = ("proposed", "accepted", "superseded", "retired")
REQUIRED = ("title", "date", "status", "review_by", "evidence")
KNOWN = {*REQUIRED, "supersedes", "retested"}
DATE = r"\d{4}-\d{2}-\d{2}"
DATED = {"date": DATE, "review_by": DATE, "retested": DATE + r"\s+\S.*"}
KEY_LINE = re.compile(r"([A-Za-z_][\w-]*):(?:\s+(.*))?")
ITEM_LINE = re.compile(r"\s*-\s+([^\s#].*)")
FORM = "want 'key: value' or a '- item' under a list key; quote values holding ': '"


def parse_date(text: str, pattern: str = DATE) -> dt.date:
    """Strict: `date.fromisoformat` alone also takes 20261024 and ISO week dates."""
    if not re.fullmatch(pattern, text):
        raise ValueError(text)
    return dt.date.fromisoformat(text[:10])


def scalar(raw: str) -> str | None:
    """Unquote a value; None if unquoted text holds ': ', which plain YAML rejects."""
    raw = raw.strip()
    if len(raw) > 1 and raw[0] == raw[-1] and raw[0] in "'\"":
        return raw[1:-1].strip()
    raw = re.sub(r"(^|\s)#.*", "", raw).strip()
    return None if ": " in raw or raw.endswith(":") else raw


def frontmatter(text: str) -> tuple[dict[str, str | list[str]], list[str]]:
    """Parse the block between the first two '---' lines into (fields, problems)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, ["frontmatter missing: the first line must be '---'"]
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
    if not end:
        return {}, ["frontmatter malformed: no closing '---' line"]
    fields: dict[str, str | list[str]] = {}
    problems: list[str] = []
    key = ""
    for n in range(1, end):
        line, at = lines[n], f"frontmatter line {n + 1}"
        item, pair = ITEM_LINE.fullmatch(line), KEY_LINE.fullmatch(line)
        target = fields.get(key)
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if item and isinstance(target, list) and (value := scalar(item[1])):
            target.append(value)
        elif pair and pair[1] in fields:
            problems.append(f"{at}: duplicate key {pair[1]!r}")
        elif pair and (value := scalar(pair[2] or "")) is not None:
            key = pair[1]
            fields[key] = value or []  # an empty value opens a '- item' list
        else:
            problems.append(f"{at}: {FORM}: {line.strip()!r}")
    return fields, problems


def check(path: Path, root: Path, today: dt.date) -> tuple[str, list[str]]:
    """Return (status, problems) for one decision record."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    fields, problems = frontmatter(text)
    if problems and not fields:
        return "", problems
    got = {k: v for k, v in fields.items() if v}  # an empty optional key is absent
    problems += [f"unknown key {k!r}" for k in fields if k not in KNOWN]
    problems += [f"missing required key {k!r}" for k in REQUIRED if k not in got]
    problems += [
        f"{k} must be " + ("a '- item' list" if k == "evidence" else "one value")
        for k, v in got.items()
        if k in KNOWN and isinstance(v, list) != (k == "evidence")
    ]
    values = {k: v for k, v in got.items() if isinstance(v, str)}
    dates: dict[str, dt.date] = {}
    for key, pattern in DATED.items():
        if key in values:
            try:
                dates[key] = parse_date(values[key], pattern)
            except ValueError:
                shape = "YYYY-MM-DD <result>" if key == "retested" else "YYYY-MM-DD"
                problems.append(f"{key} must be '{shape}', got {values[key]!r}")
    status = values.get("status", "")
    if status and status not in STATUSES:
        problems.append(f"status {status!r} is not one of {', '.join(STATUSES)}")
    target = values.get("supersedes")
    if target:
        # supersedes must name the decision record it replaces: a non-template .md under
        # docs/decisions/, inside the repo. The containment leg blocks path traversal
        # (`../../etc/passwd`) and absolute paths; the directory/extension leg blocks any
        # other in-repo file (`README.md`, a source file) that would let a replacement
        # claim a transition without naming a real predecessor record.
        root_resolved = root.resolve()
        decisions_dir = (root / DECISIONS).resolve()
        candidate = (root / target).resolve()
        inside_repo = candidate == root_resolved or root_resolved in candidate.parents
        under_decisions = decisions_dir in candidate.parents
        is_record = (
            under_decisions and candidate.suffix == ".md" and candidate.name not in SKIP
        )
        if not inside_repo:
            problems.append(
                f"supersedes {target!r}: must be a repo-relative path inside the repository"
            )
        elif not is_record:
            problems.append(
                f"supersedes {target!r}: must name a decision record under "
                f"{DECISIONS.as_posix()}/ (a non-template .md file)"
            )
        elif candidate == path.resolve():
            problems.append(f"supersedes {target!r}: a record cannot supersede itself")
        elif not candidate.is_file():
            problems.append(f"supersedes {target!r}: no such repo-relative file")
        elif status == "accepted":
            # An accepted replacement must leave no conflicting active predecessor: the
            # record it supersedes must itself be marked 'superseded' (docs/decisions/
            # README.md), else two active decisions coexist while the lineage reads valid.
            pred_fields, _ = frontmatter(
                candidate.read_text(encoding="utf-8-sig", errors="replace")
            )
            pred_status = pred_fields.get("status")
            if pred_status != "superseded":
                problems.append(
                    f"supersedes {target!r}: an accepted record's predecessor must have "
                    f"status 'superseded', got {pred_status or 'none'!r}"
                )
    if dates.get("retested", today) > today:
        problems.append(f"retested is dated after today ({today})")
    review_by = dates.get("review_by", today)
    if status == "accepted" and dates.get("retested", dt.date.min) < review_by < today:
        problems.append(
            f"accepted and past review_by {review_by}: re-test it and add 'retested: "
            f"YYYY-MM-DD <result>' dated {review_by} or later, or supersede it"
        )
    return status, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the docs/decisions/ records.")
    parser.add_argument("--today", type=parse_date, default=dt.date.today())
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    folder = args.root / DECISIONS
    if not folder.is_dir():
        print(f"cannot check: {folder} is not a directory", file=sys.stderr)
        return 2
    records = sorted(p for p in folder.glob("*.md") if p.name not in SKIP)
    problems = [] if records else [f"{DECISIONS.as_posix()}: no decision records"]
    statuses: Counter[str] = Counter()
    for path in records:
        status, found = check(path, args.root, args.today)
        statuses[status] += 1
        problems += [f"{path.relative_to(args.root).as_posix()}: {p}" for p in found]
    if problems:
        print("\n".join(problems))
        return 1
    counts = ", ".join(f"{statuses[s]} {s}" for s in STATUSES)
    print(f"decisions OK: {len(records)} record(s) as of {args.today} ({counts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
