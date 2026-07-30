#!/usr/bin/env python3
"""PostToolUse(Edit|Write|MultiEdit): per-edit secret gate + fast syntax/lint check.

After each file edit, runs a FAST, time-boxed (~8 s) checker on just the
changed file and injects any failures immediately — addressing them at the
cheapest point in the edit-fix loop.

Write-path secret gate (AGENTS.md §9)
─────────────────────────────────────
Before the linter runs, the changed file is scanned for high-confidence
hardcoded-credential shapes (AWS access key IDs, PEM/PGP private-key armor,
OpenAI / GitHub / Slack / Google / Stripe keys).  A match blocks the write
under a four-part contract: exit 2, the reason on stderr, stdout clean, and
the reason names the credential TYPE and line number without ever echoing the
matched bytes.  All four are asserted by
``test_secrets.py::test_main_blocks_secret_write``, and each was verified by
inverting it in this file and confirming the suite goes red.  The no-echo part
is the load-bearing one: this hook's stderr is injected into agent context, so
a reason that quoted the offending text would print the very credential it
caught.  A credential-shaped string is treated as a placeholder (and allowed)
when a marker such as ``EXAMPLE`` or ``YOUR_KEY`` appears on the same line
WITHIN 24 characters of the match; a marker further away is incidental prose
and does not exempt.

Unlike the linter the secret gate is NOT skipped for scratchpad/temp paths —
a credential written there still lands on disk.  It is skipped for files over
MAX_FILE_BYTES, consistent with the rest of the hook.

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
    syntax errors              → exit 2, reason on STDERR, stdout clean
  secret gate match            → exit 2, reason on STDERR, stdout clean

  No block-decision JSON is ever emitted on the exit-2 path and none can be:
  Claude Code ignores stdout at exit 2, which is why the reason goes to stderr
  and why every exit-2 case in ``test_check.py`` asserts stdout is EMPTY.  An
  earlier revision of this docstring advertised such a payload; it never existed
  and ``test_docstring_promises_no_decision_json_the_exit_2_path_cannot_emit``
  now pins the prose to the measured behaviour.

  §6 reconciliation — exit 2 here is NOT a block.  This is PostToolUse: the edit
  has already been written and nothing is reverted or denied; exit 2 is simply
  the only channel Claude Code reliably surfaces to the model after the fact.
  §6's "irreversible/dangerous only" restriction governs *denying an operation*,
  which is a PreToolUse capability this hook does not use.  The one genuinely
  §6-listed condition it does carry ("secrets in code") uses the same channel.

FAIL-OPEN: every unhandled error → exit 0, no output.
Opt-outs:  env  PER_EDIT_CHECK=off    (any capitalisation) — whole hook
           env  PER_EDIT_SECRETS=off  (any capitalisation) — secret gate only
           file .disabled  (sentinel in this hook directory) — whole hook
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

HOOKDIR = os.path.dirname(os.path.abspath(__file__))
MAX_FILE_BYTES = 512 * 1024  # 512 KB — skip generated/binary-heavy files
TIMEOUT = 8  # seconds — hard cap per subprocess call


# ── write-path secret gate (AGENTS.md §9) ────────────────────────────────────

# Characters within which a placeholder marker on the SAME line exempts a
# credential-shaped match.  Bounded on purpose: a real key sharing a line with
# an unrelated far-away "# example" comment must still block.
MARKER_PROXIMITY = 24

# Lowercase substrings that mark a credential-shaped string as documentation
# or a fill-me-in placeholder rather than a live credential.
PLACEHOLDER_MARKERS = (
    "example",
    "placeholder",
    "your_key",
    "your-key",
    "yourkey",
    "your_token",
    "your-token",
    "redacted",
    "dummy",
    "fake",
    "notarealkey",
    "not_a_real_key",
)

# High-confidence credential shapes only.  Every entry must be specific enough
# that a match is almost certainly a real credential — this gate BLOCKS, so a
# false positive costs the user an edit.  Generic "password = ..." heuristics
# are deliberately excluded.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS access key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "private key material",
        re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"),
    ),
    ("OpenAI API key", re.compile(r"\bsk-[A-Za-z0-9_-]{40,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("Google API key", re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b")),
    ("Stripe secret key", re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}\b")),
)


def _is_placeholder(line: str, start: int, end: int) -> bool:
    """True when a placeholder marker sits within MARKER_PROXIMITY of the match.

    ``start``/``end`` are the match span in *line*.  A marker that overlaps the
    match has gap 0 -- which is the common case for published documentation
    samples, whose own trailing ``EXAMPLE`` is itself one of
    ``PLACEHOLDER_MARKERS``.  The literal sample string is deliberately NOT
    quoted here: the repo SAST rule ``generic-aws-access-key-id`` matches it and
    cannot distinguish a credential from prose about one.  See
    ``test_aws_example_exempt`` for the executable form of this case.
    """
    low = line.lower()
    for marker in PLACEHOLDER_MARKERS:
        pos = low.find(marker)
        while pos != -1:
            gap = max(start - (pos + len(marker)), pos - end, 0)
            if gap <= MARKER_PROXIMITY:
                return True
            pos = low.find(marker, pos + 1)
    return False


def _scan_secrets(fp: str) -> str | None:
    """Scan *fp* for hardcoded-credential shapes.

    Returns a human-readable reason for the FIRST non-placeholder match, or
    ``None`` when the file is clean / too large / unreadable.  The reason names
    the credential type and line number and NEVER echoes the matched bytes.
    Fail-open: any unexpected error → ``None``.
    """
    try:
        if os.path.getsize(fp) > MAX_FILE_BYTES:
            return None
        with open(fp, encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, start=1):
                for label, pat in SECRET_PATTERNS:
                    for m in pat.finditer(line):
                        if _is_placeholder(line, m.start(), m.end()):
                            continue
                        return f"{label} on line {lineno}"
        return None
    except Exception:
        return None


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

        # ── write-path secret gate (AGENTS.md §9) ────────────────────────────
        # Runs BEFORE the scratchpad skip and the linter: a credential written
        # to a throwaway path still lands on disk, and a hardcoded secret is a
        # higher-severity finding than any lint issue.
        if os.environ.get("PER_EDIT_SECRETS", "").lower() != "off":
            reason = _scan_secrets(fp)
            if reason:
                print(
                    f"[per-edit-check] BLOCKED: {reason} of "
                    f"{os.path.basename(fp)} looks like a hardcoded credential.\n"
                    "Secrets must never be written into source (AGENTS.md §9) — "
                    "read it from an environment variable or a secret manager.\n"
                    "If this is a placeholder, mark the line (EXAMPLE / "
                    "YOUR_KEY / PLACEHOLDER); to override, set "
                    "PER_EDIT_SECRETS=off.",
                    file=sys.stderr,
                )
                return 2

        # ── skip throwaway scratch trees (not deliverables) ──────────────────
        _norm = fp.replace("\\", "/").lower()
        if any(
            seg in _norm for seg in ("/scratchpad/", "/temp/claude/", "/.write-probe")
        ):
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
