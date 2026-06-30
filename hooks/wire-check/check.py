#!/usr/bin/env python3
r"""wire-check/check.py — Stop / SubagentStop hook. Reachability (anti-slop) gate.

Over the SESSION GIT DIFF (uncommitted changes vs HEAD + untracked source files), it
builds a lightweight static reference graph with ripgrep and flags:

  (A) DEAD / NOT-YET-WIRED CODE: a symbol the agent ADDED this session — an exported
      function/class, a route, or a UI handler (handleX / onX) — that is referenced
      0 times anywhere else in the repo (the "dead button / built-but-not-wired" smell).

  (B) DUPLICATE-VERSION: a session-added FILE or SYMBOL named *_v2 / *_new / *_copy /
      *_2 / *V2 whose base (v1) has NO file and NO live reference — the coupons_v2-with-
      no-coupons archetype (a fork that shadow-builds instead of replacing v1).

It injects a non-accusatory "WIRING CHECK: ... referenced 0x — dead code or not-yet-
wired?" so the agent reconciles it. It NEVER blocks (a maybe-dead symbol is not a
dangerous op; many are public API) — inject-only, exit 0.

THE GAP IT FILLS (NON-DUPLICATIVE vs B1):
  * orphan-commit catches an untracked imported FILE after `git commit` (file-level,
    commit-triggered). wire-check catches orphan CODE (symbol/route/handler-level) over
    the working-tree diff, no commit required — it extends orphan-commit from files to
    symbols, exactly as the AGENTIC-PERFECTION-PLAN T1.3 specifies.
  * dark-surface needs a STUB MARKER + a completion claim. wire-check flags fully-
    implemented, marker-free, claim-free code that simply nothing calls.

LIMITATION (honest): the diff is working-tree-vs-HEAD, so work already COMMITTED earlier
this session is not re-analyzed (Stop usually fires before the commit). Set
WIRE_CHECK_BASE=<git-ref> to diff against a recorded session-start ref instead.

FAIL-OPEN (try/except -> exit 0). Anti-loop via stop_hook_active. Needs git + (ripgrep
or a stdlib fallback). Opt-out: WIRE_CHECK=off in env, or hooks/wire-check/.disabled.

settings.json (Stop, no matcher — also valid under SubagentStop):
  {"type":"command",
   "command":"python C:/Users/Prekzursil/.claude/hooks/wire-check/check.py",
   "timeout":25,"statusMessage":"Wire-check reachability (dead-code / _v2 gate)"}
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
MAX_SYMBOLS = 40
MAX_FINDINGS = 6
SRC_EXT = (
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
TEST_HINT = re.compile(
    r"(^|[/\\])(test_|tests?[/\\]|.*\.test\.|.*\.spec\.|conftest)", re.IGNORECASE
)

# Top-level definitions (line-anchored over the added-line block).
_DEF_TOPLEVEL = re.compile(
    r"^(?:export\s+(?:default\s+)?)?(?:async\s+)?"
    r"(?:def|class|function|interface|type|enum|struct|trait)\s+([A-Za-z_]\w{2,})",
    re.MULTILINE,
)
_DEF_EXPORT_CONST = re.compile(
    r"^\s*export\s+(?:const|let)\s+([A-Za-z_]\w{2,})\s*[=:]", re.MULTILINE
)
# UI handlers by naming convention (may be indented inside a component).
_HANDLER = re.compile(
    r"\b(?:const|let|var|function)\s+(handle[A-Z]\w+|on[A-Z]\w{2,})\b"
)
# Route path literals.
_ROUTE = re.compile(
    r"(?:\.(?:get|post|put|delete|patch|use|route|all)\s*\(|@(?:app|router|bp)\.route\s*\(|"
    r"\bpath\s*\(|<Route\b[^>]*\bpath=)\s*['\"]([^'\"]{1,80})['\"]",
    re.IGNORECASE,
)
# Version-suffix detector (requires a separator or Vn — avoids base64/sha256).
_VERSUF = re.compile(
    r"^(?P<base>.+?)(?:[._-](?:v\d+|new|copy|old|final|backup|orig|\d+)|V\d+)$",
    re.IGNORECASE,
)


def _git(cwd: str, *args, timeout=10):
    try:
        r = subprocess.run(
            ["git", "-C", cwd, *args], capture_output=True, text=True, timeout=timeout
        )
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def _rg_lines(cwd: str, pattern: str, fixed=False, timeout=8) -> list[str]:
    try:
        args = ["rg", "-w", "-n", "--no-heading", "-S"]
        if fixed:
            args = ["rg", "-F", "-n", "--no-heading"]
        args += ["-g", "!.git", pattern, cwd]
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if r.returncode in (0, 1):
            return [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    except Exception:
        pass
    # stdlib fallback (bounded) — only used if ripgrep is unavailable.
    out: list[str] = []
    rx = re.compile(
        (re.escape(pattern) if fixed else r"\b" + re.escape(pattern) + r"\b")
    )
    try:
        for dp, dns, fns in os.walk(cwd):
            dns[:] = [
                d
                for d in dns
                if d
                not in (
                    ".git",
                    "node_modules",
                    ".venv",
                    "venv",
                    "__pycache__",
                    "dist",
                    "build",
                    "target",
                    ".next",
                )
            ]
            for fn in fns:
                if not fn.lower().endswith(SRC_EXT):
                    continue
                fp = os.path.join(dp, fn)
                try:
                    for i, line in enumerate(
                        Path(fp).read_text("utf-8", "replace").splitlines(), 1
                    ):
                        if rx.search(line):
                            out.append(f"{fp}:{i}:{line}")
                            if len(out) > 4000:
                                return out
                except Exception:
                    continue
    except Exception:
        pass
    return out


def _changed_files(cwd: str) -> list[tuple[str, bool]]:
    """Return [(abs_path, is_untracked)] for changed SOURCE files (working tree vs HEAD)."""
    base = os.environ.get("WIRE_CHECK_BASE", "")
    files: dict[str, bool] = {}
    names = _git(cwd, "diff", "--name-only", base or "HEAD") or ""
    for n in names.splitlines():
        n = n.strip()
        if n.lower().endswith(SRC_EXT):
            files[os.path.join(cwd, n)] = False
    status = _git(cwd, "status", "--porcelain") or ""
    for line in status.splitlines():
        if line.startswith("??"):
            p = line[2:].strip().strip('"')
            if p.lower().endswith(SRC_EXT):
                files[os.path.join(cwd, p)] = True
    return [(p, u) for p, u in files.items()]


def _added_block(cwd: str, abs_path: str, untracked: bool) -> str:
    """Return the text of lines ADDED this session for a file (best-effort)."""
    if untracked:
        try:
            return Path(abs_path).read_text("utf-8", "replace")
        except Exception:
            return ""
    base = os.environ.get("WIRE_CHECK_BASE", "") or "HEAD"
    rel = os.path.relpath(abs_path, cwd)
    diff = _git(cwd, "diff", "--unified=0", base, "--", rel) or ""
    added = []
    for ln in diff.splitlines():
        if ln.startswith("+") and not ln.startswith("+++"):
            added.append(ln[1:])
    return "\n".join(added)


def _extract(block: str):
    """Return (symbols:set[str], routes:set[str]) from an added-line block."""
    syms, routes = set(), set()
    for rx in (_DEF_TOPLEVEL, _DEF_EXPORT_CONST, _HANDLER):
        for m in rx.finditer(block):
            name = m.group(1)
            if name and not name.startswith("_") and len(name) >= 3:
                syms.add(name)
    for m in _ROUTE.finditer(block):
        p = m.group(1)
        if len(p) >= 4 and re.search(r"[A-Za-z]", p):
            routes.add(p)
    return syms, routes


def _ref_count(cwd: str, name: str) -> int:
    """Count NON-definition references to `name` across the repo."""
    def_re = re.compile(
        r"(?:def|class|function|interface|type|enum|struct|trait|const|let|var)\s+"
        + re.escape(name)
        + r"\b"
        r"|\b" + re.escape(name) + r"\s*[=:]\s*(?:\(|async|function)"
    )
    refs = 0
    for line in _rg_lines(cwd, name):
        text = line.split(":", 2)[-1]
        if def_re.search(text):
            continue  # a definition of the symbol, not a use
        refs += 1
    return refs


def _literal_count(cwd: str, lit: str) -> int:
    return len(_rg_lines(cwd, lit, fixed=True))


def _base_is_live(cwd: str, base: str, all_files: list[str]) -> bool:
    blow = base.lower()
    for fp, _u in all_files:
        stem = os.path.splitext(os.path.basename(fp))[0].lower()
        if stem == blow:
            return True
    # any file in the repo named base.* ?
    for line in _rg_lines(cwd, base):  # cheap: name appears anywhere as a word
        return True
    return False


def analyze(cwd: str) -> list[str]:
    changed = _changed_files(cwd)
    if not changed:
        return []
    findings: list[str] = []
    seen_sym: set[str] = set()
    checked = 0

    # (A) dead/unwired added symbols + routes
    for abs_path, untracked in changed:
        if TEST_HINT.search(abs_path):
            continue  # don't flag test-local helpers as "dead production code"
        block = _added_block(cwd, abs_path, untracked)
        if not block:
            continue
        syms, routes = _extract(block)
        for name in sorted(syms):
            if name in seen_sym or checked >= MAX_SYMBOLS:
                continue
            seen_sym.add(name)
            checked += 1
            if _ref_count(cwd, name) == 0:
                findings.append(
                    f"`{name}()` (added in {os.path.basename(abs_path)}) is referenced 0x"
                )
            if len(findings) >= MAX_FINDINGS:
                return findings
        for rp in sorted(routes):
            if checked >= MAX_SYMBOLS:
                break
            checked += 1
            if _literal_count(cwd, rp) <= 1:
                findings.append(
                    f"route '{rp}' (added in {os.path.basename(abs_path)}) is linked/navigated 0x"
                )
            if len(findings) >= MAX_FINDINGS:
                return findings

    # (B) duplicate-version: _v2/_new/_copy file or symbol with no live v1
    dup_seen: set[str] = set()
    for abs_path, _u in changed:
        stem = os.path.splitext(os.path.basename(abs_path))[0]
        m = _VERSUF.match(stem)
        if m:
            base = m.group("base")
            if base and base.lower() not in dup_seen and len(base) >= 3:
                dup_seen.add(base.lower())
                if not _base_is_live(cwd, base, changed):
                    findings.append(
                        f"`{os.path.basename(abs_path)}` looks like a versioned fork but no live "
                        f"v1 `{base}` (file or reference) exists"
                    )
            if len(findings) >= MAX_FINDINGS:
                return findings
    # versioned SYMBOLS too
    for name in list(seen_sym):
        m = _VERSUF.match(name)
        if m:
            base = m.group("base")
            if base and base.lower() not in dup_seen and len(base) >= 3:
                dup_seen.add(base.lower())
                if _ref_count(cwd, base) == 0:
                    findings.append(
                        f"symbol `{name}` looks versioned but base `{base}` is referenced 0x"
                    )
            if len(findings) >= MAX_FINDINGS:
                break
    return findings


def main() -> int:
    try:
        if DISABLED.exists() or os.environ.get("WIRE_CHECK", "").lower() in (
            "off",
            "0",
            "false",
        ):
            return 0
        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            return 0
        if data.get("stop_hook_active"):
            return 0  # anti-loop
        cwd = str(data.get("cwd") or os.getcwd())
        if _git(cwd, "rev-parse", "--is-inside-work-tree", timeout=5) is None:
            return 0  # not a git repo -> nothing reliable to diff
        findings = analyze(cwd)
        if not findings:
            return 0
        shown = "; ".join(findings[:MAX_FINDINGS])
        msg = (
            f"[wire-check] WIRING CHECK — code you added this session looks unreferenced: "
            f"{shown}. Is it dead code, or built-but-not-yet-wired? Wire it into a live call "
            f"path (import/route/handler), delete it, or confirm it is an intentional public "
            f"API / entry point. (File-level untracked imports are covered separately by "
            f"orphan-commit.)"
        )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "Stop",
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
