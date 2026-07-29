#!/usr/bin/env python3
r"""dup-guard/guard.py — PreToolUse hook (matcher: Write). Search-before-build.

Before the agent WRITES A NEW FILE, checks whether a file with the same basename —
or whose primary symbol (first top-level class/def/export) — already exists ELSEWHERE
in the repo, and injects: "DUP-GUARD: a <name> already exists at <path> — extend it or
confirm this is intentionally new." Stops the agent reimplementing something that is
already there (the reflexive "write utils.py" when one exists two dirs over).

NON-DUPLICATIVE vs B1 and the sibling wire-check:
  - orphan-commit: untracked imported FILE after `git commit` (post-hoc, file-level).
  - wire-check (sibling, Stop): *_v2/_new/_copy suffix with no live v1, post-write.
  - dup-guard: PRE-write, proactive, exact basename/symbol COLLISION — a different axis
    (reimplement-vs-extend) at a different time (before the write happens).

Only fires for genuinely NEW files (skips overwrites of an existing path) and skips
structurally-recurring basenames (__init__.py, index.ts, mod.rs, Dockerfile, ...).
Throttled once per (basename|symbol) per session. Inject-only — a duplicate write is
not dangerous (AGENTS.md s6) so NO exit-2 block; the agent decides.

FAIL-OPEN (try/except -> exit 0). Uses ripgrep when present, else a bounded os.walk.
Opt-out: DUP_GUARD=off in env, or a hooks/dup-guard/.disabled file.

settings.json (PreToolUse, matcher "Write"):
  {"type":"command",
   "command":"python C:/Users/Prekzursil/.claude/hooks/dup-guard/guard.py",
   "timeout":8,"statusMessage":"Dup-guard (search-before-build)"}
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
WARN_ROOT = Path(
    os.environ.get(
        "DUP_GUARD_ROOT", str(Path(tempfile.gettempdir()) / "claude-dup-guard")
    )
)
MAX_FILES = 15000

# Basenames that legitimately recur once per directory -> never a "duplicate".
_RECUR = {
    "__init__.py",
    "__main__.py",
    "conftest.py",
    "setup.py",
    "index.ts",
    "index.tsx",
    "index.js",
    "index.jsx",
    "index.mjs",
    "mod.rs",
    "lib.rs",
    "main.rs",
    "main.go",
    "makefile",
    "dockerfile",
    "readme.md",
    "package.json",
    "tsconfig.json",
    ".gitignore",
    "go.mod",
    "cargo.toml",
    "pyproject.toml",
    "requirements.txt",
}
_IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "dist",
    "build",
    ".next",
    "target",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "site-packages",
    ".tox",
    "coverage",
    ".idea",
    ".vscode",
    "vendor",
    ".cache",
}
_SRC_EXT = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".go",
    ".rs",
    ".java",
    ".rb",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".kt",
    ".swift",
    ".scala",
    ".php",
)

_PRIMARY_SYMBOL = re.compile(
    r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?"
    r"(?:class|def|function|interface|struct|enum|trait)\s+([A-Za-z_]\w{2,})",
    re.MULTILINE,
)
_EXPORT_CONST = re.compile(
    r"^\s*export\s+(?:const|let|var)\s+([A-Za-z_]\w{2,})\s*=", re.MULTILINE
)


def _warn_file(session_id: str) -> Path:
    WARN_ROOT.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in str(session_id))[
        :80
    ]
    return WARN_ROOT / f"{safe or 'unknown'}.json"


def _already(session_id: str, key: str) -> bool:
    f = _warn_file(session_id)
    try:
        return f.exists() and key in json.loads(
            f.read_text(encoding="utf-8", errors="replace")
        )
    except Exception:
        return False


def _mark(session_id: str, key: str) -> None:
    f = _warn_file(session_id)
    data = []
    try:
        if f.exists():
            loaded = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            if isinstance(loaded, list):
                data = loaded
    except Exception:
        data = []
    if key not in data:
        data.append(key)
    try:
        f.write_text(json.dumps(data[-500:]), encoding="utf-8")
    except Exception:
        pass


def _list_files(root: str) -> list[str]:
    """List repo files (prefer ripgrep --files; fall back to a bounded os.walk)."""
    try:
        r = subprocess.run(
            ["rg", "--files", "--hidden", "-g", "!.git", root],
            capture_output=True,
            text=True,
            timeout=6,
        )
        if r.returncode in (0, 1) and r.stdout:
            return [ln for ln in r.stdout.splitlines() if ln.strip()][:MAX_FILES]
    except Exception:
        pass
    out: list[str] = []
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d.lower() not in _IGNORE_DIRS]
            for fn in filenames:
                out.append(os.path.join(dirpath, fn))
                if len(out) >= MAX_FILES:
                    return out
    except Exception:
        pass
    return out


def _same(a: str, b: str) -> bool:
    try:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(
            os.path.abspath(b)
        )
    except Exception:
        return a == b


def _primary_symbol(content: str) -> str | None:
    m = _PRIMARY_SYMBOL.search(content) or _EXPORT_CONST.search(content)
    return m.group(1) if m else None


def _symbol_defined_elsewhere(root: str, symbol: str, target: str) -> str | None:
    """Return a SOURCE path (other than target) that DEFINES `symbol`, if any.

    USE-vs-MENTION (L03).  The ripgrep pattern is declaration-SHAPED text, not a parse, so
    it matches just as happily inside a Markdown code fence, a design doc, a JSON fixture or
    a changelog as it does in real code.  Measured at 27fb388: writing a new
    ``probe_only_data_version_control.py`` containing ``class DataVersionControl:`` was told
    the symbol "is already defined at
    ``.agents/skills/llm-security/rules/data-poisoning.md``" -- a documentation sample that
    cannot be extended or imported, so the hook's own recommendation
    ("Extend / import the existing one", main() below) was impossible to follow.

    ``_SRC_EXT`` is the same source-role predicate the basename branch already uses; applying
    it here makes the two branches agree.  The filter runs on the RESULT list rather than only
    as an rg ``-g`` glob so the guard holds whatever ripgrep's globbing does, and the loop
    keeps scanning: a real source definition later in rg's output is still returned.
    """
    pat = (
        r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?(?:class|def|function|interface|struct|enum|trait|const|let|var|type)\s+"
        + re.escape(symbol)
        + r"\b"
    )
    globs: list[str] = ["-g", "!.git"]
    for ext in _SRC_EXT:
        globs += ["-g", f"*{ext}"]
    try:
        r = subprocess.run(
            ["rg", "-l", "--hidden", *globs, "-m", "1", pat, root],
            capture_output=True,
            text=True,
            timeout=6,
        )
        if r.returncode == 0 and r.stdout:
            for ln in r.stdout.splitlines():
                cand = ln.strip()
                if not cand or _same(cand, target):
                    continue
                if not cand.lower().endswith(_SRC_EXT):
                    continue  # prose / fixture / fence -- a mention, not a definition
                return cand
    except Exception:
        pass
    return None


def main() -> int:
    try:
        if DISABLED.exists() or os.environ.get("DUP_GUARD", "").lower() in (
            "off",
            "0",
            "false",
        ):
            return 0
        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            return 0
        if str(data.get("tool_name") or "") != "Write":
            return 0
        ti = data.get("tool_input") or {}
        if not isinstance(ti, dict):
            return 0
        file_path = str(ti.get("file_path") or ti.get("path") or "")
        if not file_path:
            return 0
        cwd = str(data.get("cwd") or os.getcwd())
        if not os.path.isabs(file_path):
            file_path = os.path.join(cwd, file_path)

        # Only NEW files (overwriting an existing path is intentional, not a dup-build).
        if os.path.exists(file_path):
            return 0
        base = os.path.basename(file_path)
        if base.lower() in _RECUR:
            return 0

        session_id = str(data.get("session_id") or "unknown")
        findings: list[str] = []

        # 1. Basename collision (only meaningful for source files).
        if base.lower().endswith(_SRC_EXT):
            key = "base:" + base.lower()
            if not _already(session_id, key):
                for fp in _list_files(cwd):
                    if os.path.basename(fp).lower() == base.lower() and not _same(
                        fp, file_path
                    ):
                        try:
                            rel = os.path.relpath(fp, cwd)
                        except Exception:
                            rel = fp
                        findings.append(
                            f"a file named `{base}` already exists at `{rel}`"
                        )
                        _mark(session_id, key)
                        break

        # 2. Primary-symbol collision (extend the existing definition, don't fork it).
        content = str(ti.get("content") or "")
        sym = _primary_symbol(content) if content else None
        if sym:
            key = "sym:" + sym
            if not _already(session_id, key):
                other = _symbol_defined_elsewhere(cwd, sym, file_path)
                if other:
                    try:
                        rel = os.path.relpath(other, cwd)
                    except Exception:
                        rel = other
                    findings.append(f"the symbol `{sym}` is already defined at `{rel}`")
                    _mark(session_id, key)

        if findings:
            joined = "; ".join(findings)
            msg = (
                f"[dup-guard] Before writing `{base}`: {joined}. Extend / import the existing "
                f"one, or confirm this is intentionally a NEW, separate implementation "
                f"(avoid reimplementing something the repo already has)."
            )
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "additionalContext": msg,
                        }
                    }
                )
            )
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
