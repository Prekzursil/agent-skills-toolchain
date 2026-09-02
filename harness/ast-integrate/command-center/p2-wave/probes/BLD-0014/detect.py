"""Contradiction detector: opposite assertion, not absence, with use-vs-mention.

Keyword search plus a mention-window. Per-decision hand-written review lives
in reviewer.py (the catalog retry-policy pivot).
"""
from __future__ import annotations

import re
from pathlib import Path

SKIP_DIR_NAMES = frozenset(
    {".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache"}
)
SKIP_REL_PREFIXES = (
    "command-center/p2-wave/probes/",
    "command-center/receipts/",
)
SUFFIXES = (
    ".md",
    ".json",
    ".yml",
    ".yaml",
    ".py",
    ".sh",
    ".ps1",
    ".js",
    ".mjs",
    ".toml",
    ".txt",
)
MAX_BYTES = 8 * 1024 * 1024

# Opposite-assertion patterns. Mere token presence of a rejected alternative
# is not enough; the line must assert the opposite as current/binding/action.
OPPOSITE = {
    "DEC-PR-ONLY": (
        re.compile(
            r"binding\s+release\s+mode\s+is\s+"
            r"(PRIVATE\s+CANARY|PUBLIC\s+MARKETPLACE)",
            re.I,
        ),
        re.compile(
            r"release\s+mode\s+is\s+"
            r"(PRIVATE\s+CANARY|PUBLIC\s+MARKETPLACE)",
            re.I,
        ),
        re.compile(
            r"release_mode\s*[:=]\s*[\"']?"
            r"(canary|marketplace|private[_-]?canary|public[_-]?marketplace)\b",
            re.I,
        ),
        re.compile(r"\bnpm\s+publish\b", re.I),
        re.compile(r"\bgh\s+release\s+create\b", re.I),
        re.compile(r"publish-to-marketplace\s*:\s*true", re.I),
        re.compile(
            r"CANARY_RELEASE_CHANNEL\s*=\s*(live|true|enabled|1)\b",
            re.I,
        ),
        re.compile(r"through the canary channel", re.I),
    ),
    "DEC-DELETE-ALL": (
        re.compile(r"retirement\s+scope\s+is\s+KEEP-SOME", re.I),
        re.compile(r"retirement\s+scope\s+is\s+DELETE-PARTIAL", re.I),
        re.compile(
            r"retirement\s+scope\s*[:=]\s*[\"']?(KEEP-SOME|DELETE-PARTIAL|SELECTIVE-KEEP)",
            re.I,
        ),
        re.compile(
            r"delete only tree [A-Z]; leave the other four trees intact",
            re.I,
        ),
    ),
    "DEC-SALVAGE-HOME": (
        re.compile(
            r"salvage home is (?!tools/lib)([A-Za-z0-9._/~-]+/)",
            re.I,
        ),
        re.compile(
            r"copy salvaged modules into (?!tools/lib)([A-Za-z0-9._/~-]+/)",
            re.I,
        ),
    ),
    "DEC-NO-REMOTE": (
        re.compile(r"\bgit\s+remote\s+add\b", re.I),
        re.compile(r"create remotes first", re.I),
        re.compile(r"create a GitHub remote for every local repo", re.I),
    ),
}

# Same-line / nearby-window markers that the opposite is quoted, rejected,
# or listed as an option rather than asserted as binding.
MENTION = re.compile(
    r"rejected|quoting|quoted|"
    r"never\s+a\s+private|"
    r"never\s+a\s+public|"
    r"never\s+create\s+remotes|"
    r"do\s+NOT\s+create\s+remotes|"
    r"must\s+not|"
    r"does\s+not\s+have|"
    r"unsatisfiable|"
    r"standing\s+in\s+for|"
    r"no\s+canary\s+(channel|path)|"
    r"no\s+marketplace\s+publish|"
    r"PR-ONLY\s*/\s*PRIVATE\s+CANARY|"
    r"under\s+PR-ONLY|"
    r"owner\s+has\s+not\s+chosen|"
    r"not\s+binding|"
    r"those\s+channels\s+are\s+not|"
    r"do\s+not\s+npm\s+publish|"
    r"never\s+npm\s+publish|"
    r"BAD_VIOLATION|"
    r"NC-PUBLIC-CANARY|"
    r"forbidden\s+canary|"
    r"--notes-file|"
    r"flag claims",
    re.I,
)

NEG_ON_LINE = re.compile(
    r"\bnever\b|\bnot\b|\bno\b|\bdon't\b|\bdo not\b|\bmust not\b|"
    r"\brejected\b|\bunsatisfiable\b|\bwithout\b",
    re.I,
)


def kind_for(rel: str) -> str:
    low = rel.replace("\\", "/").lower()
    if low.endswith((".yml", ".yaml")) or "/.github/workflows/" in low:
        return "ci-workflow"
    if low.endswith((".sh", ".ps1", ".py", ".js", ".mjs")):
        return "script"
    return "prose"


def is_comment_line(rel: str, line: str) -> bool:
    s = line.lstrip()
    if rel.endswith((".yml", ".yaml", ".sh", ".py", ".ps1", ".js", ".mjs")):
        return s.startswith("#")
    return False


def same_line_negated(line: str, match: re.Match) -> bool:
    """True when the assertion itself is negated on the same line.

    'never a private canary' must not flag. 'binding release mode is PRIVATE
    CANARY' must flag even if a later sentence on a nearby line mentions PR-ONLY.
    """
    span = line[: match.end()]
    # Negation immediately before the match, or 'never'/'not' in the matched text.
    head = line[: match.start()]
    if NEG_ON_LINE.search(match.group(0)):
        return True
    # "never a private canary" / "do not npm publish" sitting in the prefix.
    tail = head[-40:] if len(head) > 40 else head
    if re.search(
        r"(never|not|no|don't|do not|must not)\s*$",
        tail,
        re.I,
    ):
        return True
    if re.search(r"\bnever\b.{0,40}$", tail, re.I) and "canary" in match.group(0).lower():
        return True
    return False


def classify_line(decision_id: str, line: str, window: str, rel: str) -> str | None:
    """Return CONTRADICTS, USE-VS-MENTION, or None (no hit)."""
    if is_comment_line(rel, line):
        return None
    patterns = OPPOSITE.get(decision_id) or ()
    matched = None
    for pat in patterns:
        m = pat.search(line)
        if m:
            matched = m
            break
    if matched is None:
        return None
    if same_line_negated(line, matched):
        return "USE-VS-MENTION"
    # Option-list / quote windows without a positive opposite assertion.
    if MENTION.search(line) and not re.search(
        r"binding\s+release\s+mode\s+is\s+(PRIVATE\s+CANARY|PUBLIC\s+MARKETPLACE)",
        line,
        re.I,
    ):
        return "USE-VS-MENTION"
    if MENTION.search(window) and not re.search(
        r"binding\s+release\s+mode\s+is\s+(PRIVATE\s+CANARY|PUBLIC\s+MARKETPLACE)",
        line,
        re.I,
    ):
        # Strong opposite actions (npm publish, git remote add) in a CI/script
        # file are still contradictions even if a nearby comment mentions PR-ONLY.
        kind = kind_for(rel)
        if kind in {"ci-workflow", "script"} and re.search(
            r"npm\s+publish|git\s+remote\s+add|gh\s+release\s+create",
            line,
            re.I,
        ):
            return "CONTRADICTS"
        return "USE-VS-MENTION"
    return "CONTRADICTS"


def window_of(lines: list[str], idx: int, radius: int = 2) -> str:
    lo = max(0, idx - radius)
    hi = min(len(lines), idx + radius + 1)
    return "\n".join(lines[lo:hi])


def iter_files(root: Path, repo: Path) -> list[Path]:
    files: list[Path] = []
    if not root.exists():
        return files
    if root.is_file():
        return [root]
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in p.parts):
            continue
        try:
            rel = p.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            rel = p.as_posix()
        if any(rel.startswith(pref) or rel == pref.rstrip("/") for pref in SKIP_REL_PREFIXES):
            continue
        if p.suffix.lower() not in SUFFIXES:
            continue
        try:
            if p.stat().st_size > MAX_BYTES or p.stat().st_size <= 0:
                continue
        except OSError:
            continue
        files.append(p)
    return files


def scan_path(path: Path, repo: Path, decision_ids: list[str] | None = None) -> list[dict]:
    try:
        rel = path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        rel = path.as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    lines = text.splitlines()
    ids = decision_ids or list(OPPOSITE)
    hits = []
    for idx, line in enumerate(lines):
        win = window_of(lines, idx)
        for did in ids:
            cls = classify_line(did, line, win, rel)
            if cls is None:
                continue
            hits.append(
                {
                    "decision_id": did,
                    "classification": cls,
                    "path": rel,
                    "line": idx + 1,
                    "snippet": line.strip()[:240],
                    "kind": kind_for(rel),
                }
            )
    return hits


def scan_tree(root: Path, repo: Path, decision_ids: list[str] | None = None) -> dict:
    files = iter_files(root, repo)
    hits: list[dict] = []
    for p in files:
        hits.extend(scan_path(p, repo, decision_ids))
    return {
        "files_scanned": len(files),
        "hits": hits,
        "roots": [str(root)],
    }


def aggregate(decisions: list[dict], hits: list[dict], surface_named: str) -> list[dict]:
    rows = []
    for dec in decisions:
        did = dec["id"]
        own = [h for h in hits if h["decision_id"] == did]
        contra = [h for h in own if h["classification"] == "CONTRADICTS"]
        mentions = [h for h in own if h["classification"] == "USE-VS-MENTION"]
        if contra:
            classification = "CONTRADICTS"
        elif mentions:
            classification = "CONFIRMED-CONSISTENT"
            # Mentions without opposite assertions do not make a contradiction.
            # They are recorded as mention_hits; the decision is consistent.
        else:
            classification = "CONFIRMED-CONSISTENT"
        rows.append(
            {
                "decision_id": did,
                "classification": classification,
                "decision_anchor": dec["anchor"],
                "contradictions": [
                    {
                        "path": h["path"],
                        "line": h["line"],
                        "snippet": h["snippet"],
                        "kind": h["kind"],
                    }
                    for h in contra
                ],
                "search_surface_named": surface_named,
                "mention_hits": len(mentions),
            }
        )
    return rows
