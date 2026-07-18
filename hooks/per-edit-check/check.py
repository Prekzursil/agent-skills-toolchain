#!/usr/bin/env python3
"""PostToolUse(Edit|Write|MultiEdit): per-edit fast syntax/lint check.

After each file edit, runs a FAST, time-boxed (~8 s) checker on just the
changed file and injects any failures immediately — addressing them at the
cheapest point in the edit-fix loop.

Language dispatch
─────────────────
  .py           ruff check <file>   (fast linter; falls back to py_compile
                                     if ruff absent — syntax check only)
  .js/.mjs/.cjs/.jsx  node --check <file>  (syntax only; skip if node absent)
  .ts/.tsx      skipped  — tsc --noEmit too slow; node --check won't parse TS
  .json         pure-Python json.load  (always available)
  .yaml/.yml    yaml.safe_load  (skip silently if pyyaml absent)
  .rs           skipped  — cargo check too heavy for a per-edit hook

Exit protocol (AGENTS.md §6)
─────────────────────────────
  ruff lint issues             → exit 0 + additionalContext inject (soft nudge)
  py_compile / node / JSON
    syntax errors              → exit 2 + decision:block JSON (hard nudge)

FAIL-OPEN: every unhandled error → exit 0, no output.
Opt-outs:  env  PER_EDIT_CHECK=off  (any capitalisation)
           file .disabled  (sentinel in this hook directory)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

HOOKDIR = os.path.dirname(os.path.abspath(__file__))
MAX_FILE_BYTES = 512 * 1024  # 512 KB — skip generated/binary-heavy files
TIMEOUT = 8  # seconds — hard cap per subprocess call


# ── per-language checkers ────────────────────────────────────────────────────


def _check_python(fp: str) -> tuple[list[str], bool]:
    """Run ruff (preferred) or py_compile (fallback) on *fp*.

    Returns ``(issues, is_syntax_error)``.
    Fail-open: ``([], False)`` on any unexpected error.
    """
    try:
        ruff = shutil.which("ruff")
        if ruff:
            r = subprocess.run(
                [ruff, "check", fp],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TIMEOUT,
            )
            if r.returncode != 0:
                raw = (r.stdout or "") + (r.stderr or "")
                lines = [
                    ln
                    for ln in raw.splitlines()
                    # strip the "Found N error(s)." summary line — it is noise
                    if ln.strip() and not ln.lstrip().startswith("Found")
                ]
                # E999 is ruff's syntax/parse error code — treat as a hard
                # syntax break so it blocks (exit 2) just like py_compile would.
                is_syntax = any("E999" in ln for ln in lines)
                return (lines or ["lint error"]), is_syntax
            return [], False

        # fallback: py_compile (syntax check only — always available)
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", fp],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
        )
        if r.returncode != 0:
            lines = [ln for ln in (r.stderr or "").splitlines() if ln.strip()]
            return (lines or ["syntax error"]), True
        return [], False
    except Exception:
        return [], False


def _check_js(fp: str) -> tuple[list[str], bool]:
    """Run ``node --check`` on *fp* (syntax only).

    Returns ``(issues, is_syntax_error)``.
    Skip silently when node is not on PATH.
    """
    try:
        node = shutil.which("node")
        if not node:
            return [], False
        r = subprocess.run(
            [node, "--check", fp],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
        )
        if r.returncode != 0:
            lines = [ln for ln in (r.stderr or "").splitlines() if ln.strip()]
            return (lines or ["parse error"]), True
        return [], False
    except Exception:
        return [], False


def _check_json(fp: str) -> tuple[list[str], bool]:
    """Attempt json.load on *fp*; report JSONDecodeError.

    Returns ``(issues, is_syntax_error)``.
    """
    try:
        with open(fp, encoding="utf-8", errors="replace") as fh:
            json.load(fh)
        return [], False
    except json.JSONDecodeError as exc:
        return [str(exc)], True
    except Exception:
        return [], False


def _check_yaml(fp: str) -> tuple[list[str], bool]:
    """Attempt yaml.safe_load on *fp*; skip silently if pyyaml is absent.

    Returns ``(issues, is_syntax_error)``.
    """
    try:
        import yaml  # noqa: PLC0415 — conditional import

        with open(fp, encoding="utf-8", errors="replace") as fh:
            yaml.safe_load(fh)
        return [], False
    except ImportError:
        return [], False  # pyyaml not installed — skip
    except Exception as exc:
        return [str(exc)], True


def _run_check(fp: str) -> tuple[list[str], bool]:
    """Dispatch to the right checker by extension.

    Returns ``(issues, is_syntax_error)``.
    Unknown / unsupported extensions → ``([], False)`` — silent skip.
    """
    ext = os.path.splitext(fp)[1].lower()
    if ext == ".py":
        return _check_python(fp)
    if ext in (".js", ".mjs", ".cjs", ".jsx"):
        return _check_js(fp)
    if ext in (".ts", ".tsx"):
        return [], False  # tsc too slow; node --check won't parse TS
    if ext == ".json":
        return _check_json(fp)
    if ext in (".yaml", ".yml"):
        return _check_yaml(fp)
    if ext == ".rs":
        return [], False  # cargo check too heavy for per-edit
    return [], False


# ── main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    try:
        # ── opt-outs ──────────────────────────────────────────────────────────
        if os.environ.get("PER_EDIT_CHECK", "").lower() == "off":
            return 0
        if os.path.exists(os.path.join(HOOKDIR, ".disabled")):
            return 0

        # ── gate: only for file-editing tools ────────────────────────────────
        if data.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
            return 0

        fp = (data.get("tool_input") or {}).get("file_path")
        if not fp:
            return 0
        if not os.path.isfile(fp):
            return 0

        # ── skip throwaway scratch trees (not deliverables) ──────────────────
        _norm = fp.replace("\\", "/").lower()
        if any(seg in _norm for seg in ("/scratchpad/", "/temp/claude/", "/.write-probe")):
            return 0

        # ── skip huge files (generated / data / compiled assets) ─────────────
        try:
            if os.path.getsize(fp) > MAX_FILE_BYTES:
                return 0
        except OSError:
            return 0

        # ── run the checker ──────────────────────────────────────────────────
        issues, is_syntax_err = _run_check(fp)
        if not issues:
            return 0

        # ── format the message ───────────────────────────────────────────────
        fname = os.path.basename(fp)
        n = len(issues)
        preview = issues[:5]
        body = "\n".join(preview)
        if n > 5:
            body += f"\n... and {n - 5} more"
        msg = f"[per-edit-check] found {n} issue(s) in {fname}:\n{body}"

        # ── emit ─────────────────────────────────────────────────────────────
        if is_syntax_err:
            # Hard block: Claude Code reads STDERR on exit 2; any JSON on
            # stdout is silently ignored at that exit code.  Write the
            # human-readable reason to stderr so the user actually sees it.
            print(msg, file=sys.stderr)
            return 2

        # Soft inject: lint issues — nudge without blocking.
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": msg,
                    }
                }
            )
        )
        return 0

    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
