#!/usr/bin/env python3
"""CC-0006 — Gate command-center prose against platform-wrong verification recipes.

Known defect class: prescribing ``git archive`` as the way to read the LF blob for
formatter/linter verification. On this estate ``git archive`` applies export-time EOL
conversion and hands back CRLF worktree bytes — the opposite of the blob
(``git cat-file -p`` / ``git show <rev>:<path>`` / ``tools/measure-guard/blobread.py``).

Use-vs-mention: a document that QUOTES the wrong recipe in order to forbid it, or that
REPORTS the defect in another file, must not be flagged. Only PRESCRIPTIVE hits fire.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent

RECIPE_ID = "git-archive-as-lf-blob"

#: Classic wrong prescription from the catalog / pre-fix RELEASE-CHECKLIST.
CLASSIC_WRONG = re.compile(
    r"(?is)against\s+the\s+\*{0,2}LF\s+blob\*{0,2}\s*\(\s*`?git\s+archive`?\s*\)"
)

#: Broader substance: git archive offered as the LF/blob/formatter verification route.
SUBSTANCE = re.compile(
    r"(?is)("
    r"(?:verify|verifying|checked?|check|run|read|obtain|get)\s+"
    r"(?:.{0,120}?)\b(?:LF\s+blob|formatter|ruff\s+format|format\s+--check)\b"
    r"(?:.{0,120}?)\bgit\s+archive\b"
    r"|"
    r"\bgit\s+archive\b(?:.{0,80}?)\b(?:LF\s+blob|formatter|ruff\s+format)\b"
    r"|"
    r"\bLF\s+blob\b(?:.{0,40}?)\bgit\s+archive\b"
    r")"
)

#: Documentary / forbid / report-the-defect framing (use-vs-mention → SILENT).
DOCUMENTARY = re.compile(
    r"(?is)("
    r"do\s+not\s+use\s+`?git\s+archive"
    r"|not\s+`?git\s+archive`?"
    r"|never\s+(?:use\s+)?`?git\s+archive"
    r"|deliberately\s+not\s+`?git\s+archive"
    r"|was\s+wrong"
    r"|prescribed\b.{0,120}?(?:until|and\s+was\s+wrong)"
    r"|returns?\s+the\s+opposite"
    r"|hands\s+back\s+(?:the\s+)?CRLF"
    r"|CRLF\s+trap"
    r"|export-time\s+EOL"
    r"|worse\s+than\s+(?:no\s+)?rule"
    r"|refused\s+here"
    r"|prescribes\s+`?git\s+archive"  # attributing the prescription to another doc
    r"|says\s+to\s+(?:run|verify|check)"
    r"|one-line\s+fix"
    r"|\bSTAYS-OPEN\b"
    r"|live\s+defect"
    r"|defect\s+class"
    r"|quotes?\s+the\s+wrong"
    r"|in\s+order\s+to\s+forbid"
    r"|DOCUMENTS?\s+the\s+defect"
    r"|documentary\s+mention"
    r")"
)

DEFAULT_ROOTS = (
    "command-center/RELEASE-CHECKLIST.md",
    "command-center/RUNBOOK.md",
    "command-center/ROLLBACK-MANIFEST.md",
    "command-center/PROGRAM-CHARTER.md",
)

DEFAULT_EXCLUDES = (
    "command-center/p2-wave/probes/CC-0006/fixtures",
    "command-center/receipts",
    "command-center/WORK-UNIT-CATALOG.json",
    "command-center/catalog-slices",
)

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "vendor",
        "htmlcov",
        "coverage",
    }
)

WINDOW = 280


@dataclass(frozen=True)
class Finding:
    recipe_id: str
    path: str
    line: int
    role: str  # "prescriptive" | "documentary"
    excerpt: str
    detail: str

    @property
    def file_line(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass
class ScanReport:
    roots: list[str]
    files_scanned: int
    prescriptive: list[Finding] = field(default_factory=list)
    documentary: list[Finding] = field(default_factory=list)
    recipe_id: str = RECIPE_ID

    @property
    def hit_count(self) -> int:
        """Gate fires only on prescriptive hits."""
        return len(self.prescriptive)

    @property
    def ok_clean(self) -> bool:
        return self.hit_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "roots": self.roots,
            "files_scanned": self.files_scanned,
            "prescriptive_count": len(self.prescriptive),
            "documentary_count": len(self.documentary),
            "hit_count": self.hit_count,
            "ok_clean": self.ok_clean,
            "prescriptive": [asdict(f) for f in self.prescriptive],
            "documentary": [asdict(f) for f in self.documentary],
        }


def _rel(path: Path, repo: Path = REPO) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _excluded(rel: str, excludes: Sequence[str]) -> bool:
    for ex in excludes:
        if rel == ex or rel.startswith(ex.rstrip("/") + "/"):
            return True
    return False


def iter_markdown_files(
    roots: Iterable[str | Path],
    *,
    repo: Path = REPO,
    excludes: Sequence[str] = DEFAULT_EXCLUDES,
) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        p = Path(root)
        if not p.is_absolute():
            p = repo / p
        if not p.exists():
            continue
        if p.is_file():
            rel = _rel(p, repo)
            if p.suffix.lower() in {".md", ".txt", ".rst"} and not _excluded(rel, excludes):
                if p not in seen:
                    files.append(p)
                    seen.add(p)
            continue
        for md in p.rglob("*"):
            if not md.is_file():
                continue
            if md.suffix.lower() not in {".md", ".txt", ".rst"}:
                continue
            if any(part in SKIP_DIR_NAMES for part in md.parts):
                continue
            rel = _rel(md, repo)
            if _excluded(rel, excludes):
                continue
            if md not in seen:
                files.append(md)
                seen.add(md)
    return sorted(files, key=lambda x: _rel(x, repo))


def _line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def _window(text: str, start: int, end: int) -> str:
    a = max(0, start - WINDOW)
    b = min(len(text), end + WINDOW)
    return text[a:b]


def _classify(window: str, matched: str) -> str:
    if DOCUMENTARY.search(window):
        return "documentary"
    # Classic wrong phrase without documentary framing is always prescriptive.
    if CLASSIC_WRONG.search(matched) or CLASSIC_WRONG.search(window):
        return "prescriptive"
    if SUBSTANCE.search(window):
        return "prescriptive"
    return "documentary"


def analyze_text(text: str, *, path: str) -> tuple[list[Finding], list[Finding]]:
    """Return (prescriptive, documentary) findings for one document body."""
    presc: list[Finding] = []
    docu: list[Finding] = []
    seen_spans: set[tuple[int, int]] = set()

    for rx in (CLASSIC_WRONG, SUBSTANCE):
        for m in rx.finditer(text):
            span = (m.start(), m.end())
            # Deduplicate overlapping spans from both regexes.
            if any(not (span[1] <= s[0] or span[0] >= s[1]) for s in seen_spans):
                continue
            seen_spans.add(span)
            win = _window(text, m.start(), m.end())
            role = _classify(win, m.group(0))
            excerpt = re.sub(r"\s+", " ", m.group(0)).strip()[:240]
            finding = Finding(
                recipe_id=RECIPE_ID,
                path=path,
                line=_line_of(text, m.start()),
                role=role,
                excerpt=excerpt,
                detail=(
                    "prescribes git archive as LF-blob verification route"
                    if role == "prescriptive"
                    else "mentions git archive / LF-blob trap in documentary framing"
                ),
            )
            if role == "prescriptive":
                presc.append(finding)
            else:
                docu.append(finding)
    return presc, docu


def analyze_file(path: Path, *, repo: Path = REPO) -> tuple[list[Finding], list[Finding]]:
    rel = _rel(path, repo)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return [], []
    return analyze_text(text, path=rel)


def scan(
    roots: Sequence[str | Path] | None = None,
    *,
    repo: Path = REPO,
    excludes: Sequence[str] = DEFAULT_EXCLUDES,
) -> ScanReport:
    root_list = [str(r) for r in (roots if roots is not None else DEFAULT_ROOTS)]
    report = ScanReport(roots=root_list, files_scanned=0)
    files = iter_markdown_files(root_list, repo=repo, excludes=excludes)
    report.files_scanned = len(files)
    for md in files:
        presc, docu = analyze_file(md, repo=repo)
        report.prescriptive.extend(presc)
        report.documentary.extend(docu)
    return report


def scan_paths(
    paths: Sequence[str | Path],
    *,
    repo: Path = REPO,
) -> ScanReport:
    """Scan an explicit file list (fixtures / planted controls)."""
    report = ScanReport(roots=[str(p) for p in paths], files_scanned=0)
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = repo / p
        if p.is_dir():
            files.extend(sorted(p.rglob("*.md")))
        elif p.is_file():
            files.append(p)
    seen: set[Path] = set()
    uniq: list[Path] = []
    for f in files:
        rp = f.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append(f)
    report.files_scanned = len(uniq)
    for md in uniq:
        presc, docu = analyze_file(md, repo=repo)
        report.prescriptive.extend(presc)
        report.documentary.extend(docu)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Optional explicit paths; default live roots")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--fail-on-hit",
        action="store_true",
        help="Exit 1 when any prescriptive hit is present (CI gate mode).",
    )
    args = parser.parse_args(list(argv if argv is not None else sys.argv[1:]))
    if args.paths:
        report = scan_paths(args.paths, repo=REPO)
    else:
        report = scan(repo=REPO)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(
            f"files_scanned={report.files_scanned} "
            f"prescriptive={len(report.prescriptive)} "
            f"documentary={len(report.documentary)} "
            f"hit_count={report.hit_count}"
        )
        for f in report.prescriptive:
            print(f"PRESCRIPTIVE {f.file_line} — {f.excerpt}")
        for f in report.documentary:
            print(f"DOCUMENTARY  {f.file_line} — {f.excerpt}")
        print("OK_CLEAN" if report.ok_clean else "HAS_WRONG_RECIPES")
    if args.fail_on_hit and report.hit_count:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
