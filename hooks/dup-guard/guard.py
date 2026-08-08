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
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
WARN_ROOT = Path(
    os.environ.get(
        "DUP_GUARD_ROOT", str(Path(tempfile.gettempdir()) / "claude-dup-guard")
    )
)
MAX_FILES = 15000
# Hard caps so this PreToolUse hook can never blow the 8s budget and DISARM the
# whole battery.  Measured 2026-08-07: with timeout=6 and an os.walk fallback the
# hook cost 13.7-15.0s whenever cwd was a home directory rather than a checkout
# (rg --files over C:/Users/Prekzursil = 4,790,886 paths / 187s, so the subprocess
# timeout ALWAYS expired and the fallback then walked to its 15000-file cap).
# Worst case now: 2.0 + 1.0 + 2.0 + interpreter start ~= 5.4s.
RG_TIMEOUT = 2.0
WALK_BUDGET = 1.0

# Set by a scan that GAVE UP inside its budget.  Without it, "scanned and found
# nothing" and "never actually scanned" are byte-identical (both emit nothing) --
# the same silent-false-pass the dispatcher's DISARMED banner exists to prevent.
_SCAN_TRUNCATED = False

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
    # A Swift package manifest recurs once per package, exactly like package.json /
    # go.mod / cargo.toml. It is also matched by _SRC_EXT (".swift"), so without this
    # entry the SECOND package in a monorepo was reported as a duplicated
    # implementation ("extend / import the existing one") -- a false positive.
    "package.swift",
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

# USE-vs-MENTION (wired 2026-08-08). `rg` reports WHICH FILES contain declaration-shaped
# text; it cannot tell a real declaration from one spelled inside a string literal. Measured
# recorded fire: writing `run_uvm_gate.py` was told the symbol `is_real_occurrence` "is
# already defined at build/B1/proofs/make_migrations.py" -- line 42 of that file, inside a
# triple-quoted CODE TEMPLATE the migration script injects into other files. Not importable,
# not extendable, so the hook's own recommendation was impossible to follow.
#
# HONEST SCOPE: this closes 1 of the 69 fires recorded on 2026-08-08. The other 68 are REAL
# declarations whose problem is cross-language homography (a Rust `let tracked`, a TS
# `export const available`), a maximally generic name (`main`, `run`, `get`, `__str__`), or a
# dead/test/vendored target. Those are NOT use-vs-mention questions and are NOT fixed here.
#
# BUDGET. This is the one hook in the battery with a confirmed DISARM history (13.8-15.0s
# against an 8s wall at a home cwd), so the added work is hard-capped: the shared module is
# imported ONLY when rg actually returned a candidate (~31-34ms), at most
# _DISCRIM_MAX_CANDIDATES files are opened, and a file larger than the discriminator's own
# ast cap is passed through unread. Hitting the cap sets _SCAN_TRUNCATED so the existing
# NOT-CHECKED banner fires -- a truncated scan must never read as a pass.
_DISCRIM_MAX_BYTES = 400_000  # == use_vs_mention._AST_MAX_BYTES
_DISCRIM_MAX_CANDIDATES = 5
_DISCRIM_KIND = "stub"  # not "marker": see _declaration_is_real

_PRIMARY_SYMBOL = re.compile(
    r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?"
    r"(?:class|def|function|interface|struct|enum|trait)\s+([A-Za-z_]\w{2,})",
    re.MULTILINE,
)
_EXPORT_CONST = re.compile(
    r"^\s*export\s+(?:const|let|var)\s+([A-Za-z_]\w{2,})\s*=", re.MULTILINE
)


def _repo_root(start: str) -> str | None:
    """Nearest ancestor of `start` holding a `.git` entry, else None.

    dup-guard's question is scoped to THE REPO ("already exists ELSEWHERE in the
    repo", module docstring).  Preferring the checkout root over a bare `cwd` keeps
    the scan proportionate when the session cwd is a home directory.  Callers MUST
    fall back to cwd when this returns None -- an earlier revision skipped instead,
    which silenced the guard for every non-git tree (it failed both FIRE cases of
    test_dup_guard.py, whose fixture repo has no .git).
    """
    try:
        p = Path(start).resolve()
    except Exception:
        return None
    for d in (p, *p.parents):
        try:
            if (d / ".git").exists():
                return str(d)
        except Exception:
            return None
    return None


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
    global _SCAN_TRUNCATED
    try:
        r = subprocess.run(
            ["rg", "--files", "--hidden", "-g", "!.git", root],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=RG_TIMEOUT,
        )
        if r.returncode in (0, 1) and r.stdout:
            return [ln for ln in r.stdout.splitlines() if ln.strip()][:MAX_FILES]
    except subprocess.TimeoutExpired:
        # Tree too big to enumerate inside the budget.  os.walk is SLOWER than rg,
        # so falling through to it made the overrun worse; give up instead.
        _SCAN_TRUNCATED = True
        return []
    except Exception:
        pass  # rg absent / failed -> the bounded walk below is the real fallback
    out: list[str] = []
    deadline = time.monotonic() + WALK_BUDGET
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d.lower() not in _IGNORE_DIRS]
            for fn in filenames:
                out.append(os.path.join(dirpath, fn))
                if len(out) >= MAX_FILES or time.monotonic() > deadline:
                    _SCAN_TRUNCATED = True
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


def _load_discriminator():
    """``hooks/_shared/use_vs_mention.py``, imported lazily and best-effort.

    Returns ``(Context, classify)`` or ``(None, None)``. Never raises: a missing shared
    module must leave this guard behaving EXACTLY as it did before it was wired.
    """
    try:
        shared = str(THIS.parent / "_shared")
        if shared not in sys.path:
            sys.path.insert(0, shared)
        from use_vs_mention import Context, classify  # noqa: PLC0415

        return Context, classify
    except Exception:  # noqa: BLE001 - no discriminator -> unchanged prior behaviour
        return None, None


def _declaration_is_real(discrim, cand: str, pattern: re.Pattern) -> bool:
    """True when `cand` really DECLARES the symbol; False when it only spells it.

    ``kind="stub"`` rather than ``"marker"``. Both silence the recorded fire identically
    today, because this caller already filters candidates to ``_SRC_EXT`` so
    ``_is_prose()`` is always False and the two kinds differ only by ``stub``'s extra
    table-cell / blockquote / struck-through mention rules. ``stub`` is chosen because it
    is a strict superset in the SAFE direction: if the ``_SRC_EXT`` filter below is ever
    relaxed, ``marker`` would flip to FIRING on a fenced ``def foo`` inside a ``.md``
    documentation sample -- reintroducing exactly the false positive that filter exists to
    close -- whereas ``stub`` returns MENTION for any prose document.

    Fail-open at every step: unreadable, oversized, unmatched or raising -> True.
    """
    Context, classify = discrim
    if Context is None or classify is None:
        return True
    try:
        if os.path.getsize(cand) > _DISCRIM_MAX_BYTES:
            return True  # above the discriminator's ast cap the exact rule degrades
        with open(cand, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except Exception:  # noqa: BLE001
        return True
    ctx = Context(file_path=cand, source="file")
    matched = False
    try:
        for m in pattern.finditer(text):
            matched = True
            if classify(text, m.span(), ctx, kind=_DISCRIM_KIND).is_real:
                return True
    except Exception:  # noqa: BLE001
        return True
    # rg matched but this scan did not reproduce it -> cannot tell -> keep the finding.
    return not matched


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
    global _SCAN_TRUNCATED
    globs: list[str] = ["-g", "!.git"]
    for ext in _SRC_EXT:
        globs += ["-g", f"*{ext}"]
    try:
        r = subprocess.run(
            ["rg", "-l", "--hidden", *globs, "-m", "1", pat, root],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=RG_TIMEOUT,
        )
        if r.returncode == 0 and r.stdout:
            discrim = None
            # `[^\S\n]*` not `\s*`: ripgrep matches line-by-line, and Python's `\s`
            # crosses newlines, which would anchor the span on the wrong line.
            py_pat = re.compile(
                r"^[^\S\n]*(?:export[^\S\n]+(?:default[^\S\n]+)?)?(?:async[^\S\n]+)?"
                r"(?:class|def|function|interface|struct|enum|trait|const|let|var|type)"
                r"[^\S\n]+" + re.escape(symbol) + r"\b",
                re.MULTILINE,
            )
            examined = 0
            for ln in r.stdout.splitlines():
                cand = ln.strip()
                if not cand or _same(cand, target):
                    continue
                if not cand.lower().endswith(_SRC_EXT):
                    continue  # prose / fixture / fence -- a mention, not a definition
                if examined >= _DISCRIM_MAX_CANDIDATES:
                    # Gave up inside the budget. Silence here is NOT a pass.
                    _SCAN_TRUNCATED = True
                    break
                examined += 1
                if discrim is None:
                    discrim = (
                        _load_discriminator()
                    )  # only paid when there IS a candidate
                if not _declaration_is_real(discrim, cand, py_pat):
                    continue  # declaration-SHAPED text, not a declaration
                return cand
    except subprocess.TimeoutExpired:
        _SCAN_TRUNCATED = True
    except Exception:
        pass
    return None


def main() -> int:
    global _SCAN_TRUNCATED
    _SCAN_TRUNCATED = False
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

        # Prefer the enclosing checkout; fall back to cwd so no tree is unscannable.
        root = _repo_root(os.path.dirname(file_path)) or _repo_root(cwd) or cwd

        session_id = str(data.get("session_id") or "unknown")
        findings: list[str] = []

        # 1. Basename collision (only meaningful for source files).
        if base.lower().endswith(_SRC_EXT):
            key = "base:" + base.lower()
            if not _already(session_id, key):
                for fp in _list_files(root):
                    if os.path.basename(fp).lower() == base.lower() and not _same(
                        fp, file_path
                    ):
                        try:
                            rel = os.path.relpath(fp, root)
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
                other = _symbol_defined_elsewhere(root, sym, file_path)
                if other:
                    try:
                        rel = os.path.relpath(other, root)
                    except Exception:
                        rel = other
                    findings.append(f"the symbol `{sym}` is already defined at `{rel}`")
                    _mark(session_id, key)

        if not findings and _SCAN_TRUNCATED:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "additionalContext": (
                                "[dup-guard] NOT CHECKED: scan root `"
                                + str(root)
                                + "` could not be enumerated inside the hook budget, "
                                "so `" + base + "` was NOT compared against existing "
                                "files. This silence is not a pass."
                            ),
                        }
                    }
                )
            )
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
