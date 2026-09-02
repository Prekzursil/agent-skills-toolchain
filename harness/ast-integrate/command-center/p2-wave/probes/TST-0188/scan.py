#!/usr/bin/env python3
"""Static scan: caret-bearing git revisions unquoted through PowerShell/cmd.

PASS for TST-0188 requires zero such call sites in the estate. The scanner
discriminates:
  * unquoted HEAD^ / tag^{commit} in .ps1/.cmd/.bat or pwsh -Command  -> hazard
  * quoted / --% / argv-array spawn                                  -> ok
  * mention in comments or docs without a git invocation             -> ignore
"""
from __future__ import annotations

import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SELF_PREFIX = "command-center/p2-wave/probes/TST-0188/"
OTHER_PROBES_PREFIX = "command-center/p2-wave/probes/"
MAX_FILE_BYTES = 2 * 1024 * 1024
# Git-helper + catalog surfaces. Other units' planted .ps1 fixtures (ADV-0118,
# AUD-0086 control-bad, …) stay in the control channel, not the estate headline.
SCAN_ROOTS = (
    "tools",
    "scripts",
    "rules",
    "platform",
    ".agents",
    "command-center",
)

CARET_REV = re.compile(
    r"(?:HEAD\^\d*|HEAD\^+|[\w./~:@-]+\^\{\w*\}|\^\{\w*\})",
    re.IGNORECASE,
)
GIT_WORD = re.compile(r"(?:^|[\s;|&(`=])git(?:\.exe)?(?=[\s\"'`])", re.IGNORECASE)
PWSH = re.compile(r"(?:^|[\s;|&(`=])(?:pwsh|powershell)(?:\.exe)?\b", re.IGNORECASE)
PWSH_CMD_FLAG = re.compile(r"(?i)(?:-Command|-c)\b")
STOP_PARSING = re.compile(r"(?i)git(?:\.exe)?\s+--%")
SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    "node_modules",
    "control-bad",
    ".venv",
    "venv",
    "egg-info",
    "_work",
    "vendor",
    "deps",
    "dist",
    ".tox",
    "site-packages",
    ".bin",
    "runtime",
}
SCAN_SUFFIXES = {
    ".py",
    ".mjs",
    ".js",
    ".cjs",
    ".ts",
    ".ps1",
    ".psm1",
    ".cmd",
    ".bat",
    ".sh",
    ".bash",
}
SHELL_SUFFIXES = {".ps1", ".psm1", ".cmd", ".bat"}
CONTROL_BAD = HERE / "fixtures" / "control-bad"
CONTROL_GOOD = HERE / "fixtures" / "control-good"


def _unquoted_regions(line: str) -> list[tuple[int, int]]:
    """Byte spans of a line that are outside quotes (simple ' \" `)."""
    regions: list[tuple[int, int]] = []
    i = 0
    n = len(line)
    start = 0
    quote: str | None = None
    while i < n:
        ch = line[i]
        if quote is None:
            if ch in {"'", '"', "`"}:
                if i > start:
                    regions.append((start, i))
                quote = ch
                start = i + 1
        elif ch == quote:
            quote = None
            start = i + 1
        elif ch == "`" and quote == '"':
            i += 2
            continue
        i += 1
    if quote is None and start < n:
        regions.append((start, n))
    return regions


def _in_regions(pos: int, regions: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in regions)


def _comment_only(path: Path, line: str) -> bool:
    s = line.lstrip()
    if not s:
        return True
    if s.startswith(("#", "//", "<!--")):
        return True
    suf = path.suffix.lower()
    if suf in {".ps1", ".psm1"} and s.startswith("#"):
        return True
    if suf in {".cmd", ".bat"} and s[:3].upper() in {"REM", "::"}:
        return True
    return False


def _looks_argv_list(line: str) -> bool:
    if re.search(r"""\[[^\]]*(['\"]git['\"]|git\s*,)""", line):
        return True
    if re.search(r"""(?:run|Popen|call|check_output|check_call)\(\s*\[""", line):
        return True
    if re.search(r"""git\(\s*\[""", line):
        return True
    return False


def _string_literals(line: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r"(['\"])(.*?)(\1)", line):
        out.append(m.group(2))
    return out


def _ps_unquoted_caret_git(text: str) -> bool:
    padded = text if text[:1].isspace() else f" {text}"
    if not GIT_WORD.search(padded) and not re.match(r"(?i)git(?:\.exe)?\s", text):
        return False
    if STOP_PARSING.search(text):
        return False
    unquoted = _unquoted_regions(text)
    return any(_in_regions(m.start(), unquoted) for m in CARET_REV.finditer(text))


def classify_line(path: Path, line: str) -> str | None:
    if not CARET_REV.search(line):
        return None
    if _comment_only(path, line):
        return None
    gitty = bool(GIT_WORD.search(line) or re.search(r"\brev-parse\b", line))
    pwsh = bool(PWSH.search(line))
    if not gitty and not pwsh:
        return None
    if STOP_PARSING.search(line):
        return "stop-parsing-ok"
    suf = path.suffix.lower()
    unquoted = _unquoted_regions(line)
    caret_unquoted = [
        m for m in CARET_REV.finditer(line) if _in_regions(m.start(), unquoted)
    ]
    if suf in SHELL_SUFFIXES:
        if not gitty:
            return None
        if not caret_unquoted:
            return "quoted-ok"
        return "unquoted-hazard"
    if pwsh and PWSH_CMD_FLAG.search(line):
        inners = _string_literals(line)
        if any(_ps_unquoted_caret_git(s) for s in inners):
            return "unquoted-hazard"
        if inners:
            return "quoted-ok"
        if gitty and caret_unquoted:
            return "unquoted-hazard"
        return None
    if _looks_argv_list(line):
        return "argv-ok"
    if suf in {".sh", ".bash"}:
        return "posix-shell-not-pwsh"
    if "shell=True" in line and gitty:
        return "posix-shell-not-pwsh"
    return "argv-or-mention-ok"


def _keep_rel(rel: str) -> bool:
    if rel.startswith(OTHER_PROBES_PREFIX) and not rel.startswith(SELF_PREFIX):
        return False
    if "/fixtures/control-bad/" in rel:
        return False
    return True


def iter_source_files(root: Path) -> list[Path]:
    root = root.resolve()
    out: list[Path] = []
    starts: list[Path] = []
    if root == REPO.resolve():
        for name in SCAN_ROOTS:
            p = root / name
            if p.exists():
                starts.append(p)
    else:
        starts.append(root)
    seen: set[Path] = set()
    for start in starts:
        if start.is_file():
            if start.suffix.lower() in SCAN_SUFFIXES:
                out.append(start)
            continue
        for dirpath, dirnames, filenames in os.walk(start):
            dirnames[:] = [
                d
                for d in dirnames
                if d not in SKIP_DIR_NAMES and not d.startswith(".git")
            ]
            for name in filenames:
                p = Path(dirpath) / name
                if p.suffix.lower() not in SCAN_SUFFIXES:
                    continue
                try:
                    if p.stat().st_size > MAX_FILE_BYTES:
                        continue
                except OSError:
                    continue
                try:
                    rel = p.resolve().relative_to(root).as_posix()
                except ValueError:
                    continue
                if not _keep_rel(rel):
                    continue
                resolved = p.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                out.append(p)
    return sorted(out)


def scan_file(path: Path) -> list[dict]:
    hits: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return hits
    rel = path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)
    for i, line in enumerate(text.splitlines(), 1):
        kind = classify_line(path, line)
        if kind is None:
            continue
        hits.append(
            {
                "path": rel,
                "line": i,
                "kind": kind,
                "text": line.strip()[:240],
            }
        )
    return hits


def scan_tree(root: Path | None = None) -> dict:
    root = root or REPO
    files = iter_source_files(root)
    all_hits: list[dict] = []
    for p in files:
        all_hits.extend(scan_file(p))
    hazards = [h for h in all_hits if h["kind"] == "unquoted-hazard"]
    return {
        "files_scanned": len(files),
        "hits": all_hits,
        "hazards": hazards,
        "hazard_count": len(hazards),
    }


def scan_controls() -> dict:
    bad = []
    for p in sorted(CONTROL_BAD.glob("*")):
        if p.is_file():
            bad.extend(scan_file(p))
    good = []
    for p in sorted(CONTROL_GOOD.glob("*")):
        if p.is_file():
            good.extend(scan_file(p))
    bad_hazards = [h for h in bad if h["kind"] == "unquoted-hazard"]
    good_hazards = [h for h in good if h["kind"] == "unquoted-hazard"]
    return {
        "bad_hits": bad,
        "good_hits": good,
        "fired_on_bad": len(bad_hazards) >= 2,
        "silent_on_good": len(good_hazards) == 0,
        "bad_hazard_count": len(bad_hazards),
        "good_hazard_count": len(good_hazards),
    }
