"""Static census of quoting hazards in scripted/generated command bodies.

Four classes from the catalog:
  * apostrophe interpolated into POSIX single quotes
  * heredoc in a command body
  * process substitution <( or >(
  * unquoted caret git-ref through PowerShell/cmd

Live tree scan skips this unit's own probe directory so fixtures stay in the
control channel, not the estate headline.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from helpers import (
    HERE,
    MAX_FILE_BYTES,
    REPO,
    SCAN_SUFFIXES,
    SELF_PREFIX,
    SHELL_SUFFIXES,
    SKIP_DIR_NAMES,
    is_self,
    relpath,
)

RULE_APOSTROPHE = "AUD0086-APOSTROPHE-POSIX-WRAP"
RULE_HEREDOC = "AUD0086-HEREDOC"
RULE_PROC = "AUD0086-PROC-SUBST"
RULE_CARET = "AUD0086-CARET-PWSH"

CMD_MARKERS = re.compile(
    r"subprocess|os\.system|os\.popen|Popen|shell\s*=\s*True|"
    r"\bbash\b|\bpwsh\b|\bpowershell\b|\bwsl\b|\bsh\s+-c|\bbash\s+-c|"
    r"Invoke-Expression|-Command\b|-lc\b",
    re.IGNORECASE,
)
CMD_VERBS = re.compile(
    r"\b(cd|git|mkdir|python3?|chmod|curl|wget|ssh|cat|echo|printf|"
    r"bash|pwsh|powershell|wsl)\b",
    re.IGNORECASE,
)
APOSTROPHE_INTERP = re.compile(
    r"'\{[^}]+\}'|"
    r"'\$[A-Za-z_][A-Za-z0-9_]*'|"
    r"f[\"'].{0,160}?'\{|"
    r"\"'\s*\+|\+\s*\"'\""
)
# 'o'reilly' — identifier, close-quote, more identifier (not `' '.join`)
APOSTROPHE_BROKEN = re.compile(r"'[A-Za-z0-9_.-]+'[A-Za-z0-9_./+-]")
HEREDOC = re.compile(r"<<[-]?\s*['\"]?[A-Za-z_][A-Za-z0-9_]*")
PROC_SUBST = re.compile(r"(?<![A-Za-z0-9_])<\(|(?<![A-Za-z0-9_])>\(")
CARET_REV = re.compile(
    r"(?:HEAD\^\d*|HEAD\^+|[\w./~:@-]+\^\{\w*\}|\^\{\w*\})",
    re.IGNORECASE,
)
GIT_WORD = re.compile(r"(?:^|[\s;|&(`=])git(?:\.exe)?(?=[\s\"'`])", re.IGNORECASE)
PWSH_WORD = re.compile(
    r"(?:^|[\s;|&(`=])(?:pwsh|powershell)(?:\.exe)?\b", re.IGNORECASE
)
STOP_PARSING = re.compile(r"(?i)git(?:\.exe)?\s+--%")
REV_PARSE = re.compile(r"\brev-parse\b")

CONTROL_BAD = HERE / "fixtures" / "control-bad"
CONTROL_GOOD = HERE / "fixtures" / "control-good"


def _comment_only(path: Path, line: str) -> bool:
    s = line.lstrip()
    if not s:
        return True
    if s.startswith("#") or s.startswith("//"):
        return True
    suf = path.suffix.lower()
    if suf in {".cmd", ".bat"} and s[:3].upper() in {"REM", "::"}:
        return True
    return False


def _unquoted_spans(line: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(line)
    start = 0
    quote: str | None = None
    while i < n:
        ch = line[i]
        if quote is None:
            if ch in {"'", '"', "`"}:
                if i > start:
                    spans.append((start, i))
                quote = ch
                start = i + 1
        elif ch == quote:
            quote = None
            start = i + 1
        i += 1
    if quote is None and start < n:
        spans.append((start, n))
    return spans


def _in_spans(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in spans)


def in_command_context(path: Path, line: str, prev: str) -> bool:
    if path.suffix.lower() in SHELL_SUFFIXES:
        return True
    blob = f"{prev}\n{line}"
    if CMD_MARKERS.search(blob):
        return True
    if CMD_VERBS.search(line) and (
        "'" in line or "<<" in line or "<(" in line or ">(" in line or "^" in line
    ):
        return True
    return False


def _hit(rel: str, line_no: int, rule: str, kind: str, snippet: str) -> dict:
    return {
        "path": rel,
        "line": line_no,
        "rule_id": rule,
        "kind": kind,
        "snippet": snippet.strip()[:220],
        "fingerprint": f"{rel}:{line_no}:{rule}",
    }


def classify_line(path: Path, rel: str, line_no: int, line: str, prev: str) -> list[dict]:
    if _comment_only(path, line):
        return []
    if not in_command_context(path, line, prev):
        return []
    hits: list[dict] = []
    suf = path.suffix.lower()

    if APOSTROPHE_INTERP.search(line) or APOSTROPHE_BROKEN.search(line):
        hits.append(_hit(rel, line_no, RULE_APOSTROPHE, "apostrophe", line))
    if HEREDOC.search(line):
        hits.append(_hit(rel, line_no, RULE_HEREDOC, "heredoc", line))
    if PROC_SUBST.search(line):
        hits.append(_hit(rel, line_no, RULE_PROC, "proc-subst", line))

    caret_ok_file = suf in {".ps1", ".psm1", ".cmd", ".bat"}
    caret_ok_line = bool(PWSH_WORD.search(line) or PWSH_WORD.search(prev))
    if (caret_ok_file or caret_ok_line) and CARET_REV.search(line):
        gitty = bool(GIT_WORD.search(line) or REV_PARSE.search(line))
        if gitty and not STOP_PARSING.search(line):
            spans = _unquoted_spans(line)
            if any(_in_spans(m.start(), spans) for m in CARET_REV.finditer(line)):
                hits.append(_hit(rel, line_no, RULE_CARET, "caret", line))
    return hits


def scan_file(path: Path, *, relative_to: Path | None = None) -> list[dict]:
    root = relative_to or REPO
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = relpath(path)
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return []
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits: list[dict] = []
    prev = ""
    for i, line in enumerate(text.splitlines(), 1):
        hits.extend(classify_line(path, rel, i, line, prev))
        prev = line
    return hits


def iter_scan_files(root: Path) -> list[Path]:
    out: list[Path] = []
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in SKIP_DIR_NAMES and not d.startswith(".git")
        ]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() not in SCAN_SUFFIXES:
                continue
            rel = relpath(p)
            if is_self(rel):
                continue
            out.append(p)
    return sorted(out)


def scan_tree(root: Path | None = None) -> dict:
    root = (root or REPO).resolve()
    files = iter_scan_files(root)
    hits: list[dict] = []
    for p in files:
        hits.extend(scan_file(p, relative_to=root))
    hits.sort(key=lambda h: h["fingerprint"])
    counts: dict[str, int] = {}
    for h in hits:
        counts[h["rule_id"]] = counts.get(h["rule_id"], 0) + 1
    return {
        "files_scanned": len(files),
        "hit_count": len(hits),
        "hits": hits,
        "fingerprints": [h["fingerprint"] for h in hits],
        "rule_counts": dict(sorted(counts.items())),
        "skipped_self_prefix": SELF_PREFIX,
    }


def _scan_dir(folder: Path) -> list[dict]:
    hits: list[dict] = []
    if not folder.is_dir():
        return hits
    for p in sorted(folder.rglob("*")):
        if p.is_file() and p.suffix.lower() in SCAN_SUFFIXES:
            hits.extend(scan_file(p, relative_to=HERE / "fixtures"))
    return hits


def scan_controls() -> dict:
    bad = _scan_dir(CONTROL_BAD)
    good = _scan_dir(CONTROL_GOOD)
    bad_rules = {h["rule_id"] for h in bad}
    required = {RULE_APOSTROPHE, RULE_HEREDOC, RULE_PROC, RULE_CARET}
    fired_on_bad = required <= bad_rules
    silent_on_good = len(good) == 0
    return {
        "fired_on_bad": fired_on_bad,
        "silent_on_good": silent_on_good,
        "pass": fired_on_bad and silent_on_good,
        "bad_hits": bad,
        "good_hits": good,
        "bad_rules": sorted(bad_rules),
        "required_rules": sorted(required),
        "missing_on_bad": sorted(required - bad_rules),
    }


def main() -> int:
    import json

    live = scan_tree()
    ctrl = scan_controls()
    doc = {"live": live, "control": ctrl, "pass": bool(ctrl.get("pass"))}
    print(json.dumps(doc, indent=2, sort_keys=True))
    if not ctrl.get("pass"):
        print("FAILED:AUD-0086-scan control did not fire-on-bad and stay silent-on-good")
        return 1
    print("SUCCESS:AUD-0086-scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
