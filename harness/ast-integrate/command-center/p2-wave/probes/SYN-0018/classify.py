"""Classify evidence anchors STABLE | LINE-MOVED | CONTENT-CHANGED | FILE-GONE.

Reads blobs only through git cat-file -p. Capture vs report are two trees
built in an isolated bare repo (hash-object + mktree).
"""
from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from blobs import (
    RECIPE_NAME,
    archive_bytes,
    cat_file,
    git_show,
    init_bare,
    write_tree,
)

CLASSES = ("STABLE", "LINE-MOVED", "CONTENT-CHANGED", "FILE-GONE")

GITATTRIBUTES = b"* text eol=crlf\n"

CAPTURE_FILES: dict[str, bytes] = {
    ".gitattributes": GITATTRIBUTES,
    "anchors/stable.md": (
        b"alpha\nbeta\nANCHORED: stable-fact-v1\ngamma\n"
    ),
    "anchors/moved.md": b"header\nANCHORED: moved-fact-v1\nfooter\n",
    "anchors/rewritten.md": b"header\nANCHORED: original-wording\nfooter\n",
    "anchors/gone.md": b"header\nANCHORED: gone-fact-v1\nfooter\n",
}

REPORT_FILES: dict[str, bytes] = {
    ".gitattributes": GITATTRIBUTES,
    "anchors/stable.md": CAPTURE_FILES["anchors/stable.md"],
    "anchors/moved.md": (
        b"INSERTED-LINE\nheader\nANCHORED: moved-fact-v1\nfooter\n"
    ),
    "anchors/rewritten.md": b"header\nANCHORED: rewritten-wording\nfooter\n",
}

FIXTURE_ANCHORS: list[dict] = [
    {
        "id": "CLAIM-STABLE-001",
        "path": "anchors/stable.md",
        "start_line": 3,
        "end_line": 3,
        "expected": "STABLE",
    },
    {
        "id": "CLAIM-MOVED-001",
        "path": "anchors/moved.md",
        "start_line": 2,
        "end_line": 2,
        "expected": "LINE-MOVED",
    },
    {
        "id": "CLAIM-REWRITE-001",
        "path": "anchors/rewritten.md",
        "start_line": 2,
        "end_line": 2,
        "expected": "CONTENT-CHANGED",
    },
    {
        "id": "CLAIM-GONE-001",
        "path": "anchors/gone.md",
        "start_line": 2,
        "end_line": 2,
        "expected": "FILE-GONE",
    },
]


def iter_lines(blob: bytes) -> list[tuple[int, int, int, bytes]]:
    """Return (line_no, start, end, content_without_newline). end exclusive."""
    rows: list[tuple[int, int, int, bytes]] = []
    start = 0
    n = 1
    length = len(blob)
    if length == 0:
        return rows
    while start < length:
        nl = blob.find(b"\n", start)
        if nl < 0:
            rows.append((n, start, length, blob[start:]))
            break
        rows.append((n, start, nl + 1, blob[start:nl]))
        start = nl + 1
        n += 1
    return rows


def span(
    blob: bytes, start_line: int, end_line: int
) -> tuple[bytes, list[int]] | None:
    rows = iter_lines(blob)
    if start_line < 1 or end_line < start_line or end_line > len(rows):
        return None
    chunk = b"\n".join(rows[i][3] for i in range(start_line - 1, end_line))
    byte_start = rows[start_line - 1][1]
    byte_end = rows[end_line - 1][2]
    return chunk, [byte_start, byte_end]


def find_span_line(blob: bytes, needle: bytes, n_lines: int) -> int | None:
    rows = iter_lines(blob)
    if n_lines < 1:
        return None
    for i in range(0, len(rows) - n_lines + 1):
        chunk = b"\n".join(rows[j][3] for j in range(i, i + n_lines))
        if chunk == needle:
            return i + 1
    return None


def classify_anchor(
    git_dir: Path,
    capture_sha: str,
    report_sha: str,
    path: str,
    start_line: int,
    end_line: int,
) -> dict:
    capture_blob = cat_file(git_dir, capture_sha, path)
    report_blob = cat_file(git_dir, report_sha, path)
    n_lines = end_line - start_line + 1
    if capture_blob is None:
        return {
            "path": path,
            "capture_sha": capture_sha,
            "report_sha": report_sha,
            "capture_byte_range": None,
            "report_byte_range": None,
            "capture_line": start_line,
            "report_line": None,
            "class": "FILE-GONE",
            "recipe": RECIPE_NAME,
            "note": "path missing at capture SHA",
        }
    cap = span(capture_blob, start_line, end_line)
    if cap is None:
        return {
            "path": path,
            "capture_sha": capture_sha,
            "report_sha": report_sha,
            "capture_byte_range": None,
            "report_byte_range": None,
            "capture_line": start_line,
            "report_line": None,
            "class": "FILE-GONE",
            "recipe": RECIPE_NAME,
            "note": "capture line range not in blob",
        }
    cap_text, cap_range = cap
    if report_blob is None:
        return {
            "path": path,
            "capture_sha": capture_sha,
            "report_sha": report_sha,
            "capture_byte_range": cap_range,
            "report_byte_range": None,
            "capture_line": start_line,
            "report_line": None,
            "class": "FILE-GONE",
            "recipe": RECIPE_NAME,
            "note": "path missing at report SHA",
        }
    same = span(report_blob, start_line, end_line)
    if same is not None and same[0] == cap_text:
        return {
            "path": path,
            "capture_sha": capture_sha,
            "report_sha": report_sha,
            "capture_byte_range": cap_range,
            "report_byte_range": same[1],
            "capture_line": start_line,
            "report_line": start_line,
            "class": "STABLE",
            "recipe": RECIPE_NAME,
            "note": "same bytes at the same line numbers",
        }
    found = find_span_line(report_blob, cap_text, n_lines)
    if found is not None and found != start_line:
        moved = span(report_blob, found, found + n_lines - 1)
        return {
            "path": path,
            "capture_sha": capture_sha,
            "report_sha": report_sha,
            "capture_byte_range": cap_range,
            "report_byte_range": None if moved is None else moved[1],
            "capture_line": start_line,
            "report_line": found,
            "class": "LINE-MOVED",
            "recipe": RECIPE_NAME,
            "note": f"identical span now at line {found}",
        }
    report_range = None if same is None else same[1]
    return {
        "path": path,
        "capture_sha": capture_sha,
        "report_sha": report_sha,
        "capture_byte_range": cap_range,
        "report_byte_range": report_range,
        "capture_line": start_line,
        "report_line": start_line if same is not None else None,
        "class": "CONTENT-CHANGED",
        "recipe": RECIPE_NAME,
        "note": "anchored bytes not present at report SHA",
    }


def class_counts(rows: list[dict]) -> dict:
    total = len(rows)
    counts = {name: 0 for name in CLASSES}
    for row in rows:
        klass = str(row.get("class") or "")
        if klass not in counts:
            raise ValueError(f"unknown-class:{klass}")
        counts[klass] += 1
    if total < 1:
        raise ValueError("empty-anchor-set")
    return {
        name: {
            "count": counts[name],
            "total": total,
            "as_string": f"{counts[name]}/{total}",
            "denominator": total,
        }
        for name in CLASSES
    }


def recipe_control(git_dir: Path, tree: str, path: str) -> dict:
    cat = cat_file(git_dir, tree, path)
    shown = git_show(git_dir, tree, path)
    if cat is None or shown is None:
        raise RuntimeError(f"recipe-control-missing:{path}")
    archived = archive_bytes(git_dir, tree, path)
    cat_crlf = cat.count(b"\r\n")
    show_crlf = shown.count(b"\r\n")
    arch_crlf = archived.count(b"\r\n")
    equal_show = cat == shown
    archive_differs = archived != cat
    archive_has_crlf = arch_crlf > 0
    blob_is_lf = cat_crlf == 0 and b"\n" in cat
    passed = (
        equal_show
        and archive_differs
        and archive_has_crlf
        and blob_is_lf
        and show_crlf == 0
    )
    return {
        "name": RECIPE_NAME,
        "forbidden": "git archive",
        "path": path,
        "tree": tree,
        "cat_file_bytes": len(cat),
        "show_bytes": len(shown),
        "archive_bytes": len(archived),
        "cat_file_crlf": cat_crlf,
        "show_crlf": show_crlf,
        "archive_crlf": arch_crlf,
        "cat_file_equals_show": equal_show,
        "archive_differs_by_crlf": archive_differs and archive_has_crlf,
        "used_for_classification": RECIPE_NAME,
        "passed": passed,
    }


class FixtureRepo:
    def __init__(self, git_dir: Path, capture_sha: str, report_sha: str) -> None:
        self.git_dir = git_dir
        self.capture_sha = capture_sha
        self.report_sha = report_sha


@contextmanager
def fixture_repo() -> Iterator[FixtureRepo]:
    with tempfile.TemporaryDirectory(prefix="syn0018-") as tmp:
        git_dir = Path(tmp) / "objects.git"
        init_bare(git_dir)
        capture = write_tree(git_dir, CAPTURE_FILES)
        report = write_tree(git_dir, REPORT_FILES)
        yield FixtureRepo(git_dir, capture, report)


def classify_fixtures(repo: FixtureRepo) -> list[dict]:
    rows: list[dict] = []
    for spec in FIXTURE_ANCHORS:
        row = classify_anchor(
            repo.git_dir,
            repo.capture_sha,
            repo.report_sha,
            spec["path"],
            int(spec["start_line"]),
            int(spec["end_line"]),
        )
        row["id"] = spec["id"]
        row["expected"] = spec["expected"]
        rows.append(row)
    return rows


def run_campaign() -> dict:
    with fixture_repo() as repo:
        rows = classify_fixtures(repo)
        control = recipe_control(
            repo.git_dir, repo.capture_sha, "anchors/stable.md"
        )
        return {
            "capture_sha": repo.capture_sha,
            "report_sha": repo.report_sha,
            "anchors": rows,
            "class_counts": class_counts(rows),
            "recipe": control,
        }


def receipt_body(doc: dict) -> dict:
    """Prefer report payload; fall back to a flat receipt."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        "recipe" in report or "anchors" in report or "class_counts" in report
    ):
        return report
    return doc
