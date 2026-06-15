#!/usr/bin/env python3
"""PostToolUse hook — async background file validator (asyncRewake demo).

PURPOSE
-------
Runs a fast, language-appropriate correctness check on every file that
Edit or Write touches.  It is registered with ``asyncRewake: true`` so it
runs OFF the critical path: Claude never waits for it.  The only time it
interrupts is when validation actually fails — exit 2 causes CC to rewake
Claude with the stderr as a system reminder.

DESIGN PROPERTIES
-----------------
- FAIL-OPEN: every code path is wrapped in try/except; any unexpected
  error → exit 0 (silent). We never false-alarm on our own bugs.
- SILENT ON SUCCESS: exit 0, no stdout, no stderr. Zero latency cost on the
  happy path.
- WINDOWS-SAFE: explicit ``encoding="utf-8", errors="replace"`` everywhere.
- OPT-OUT: set env var ``ASYNC_VALIDATE=off`` to disable completely.

LANGUAGE DISPATCH
-----------------
  .py           python -m py_compile  (syntax)
                ruff check            (lint, if ruff is on PATH)
  .js/.mjs/.cjs node --check          (V8 parse)
  .ts           node --check on .ts is not valid; tsc --noEmit is
                project-wide and far too heavy.  TS files are skipped
                (see NOTE-TS below).  If a fast TS-aware parser appears
                in your toolchain, wire it here.
  .json         json.load in-process  (no subprocess overhead)
  other         exit 0 (not applicable)

EXIT CODES
----------
  0  success, or not applicable, or internal error (fail-open)
  2  validation failure — CC's asyncRewake surfaces stderr to Claude

Stdin: PostToolUse JSON payload from Claude Code.
Relevant fields:
  tool_name   str   ("Edit" | "Write" | ...)
  tool_input  dict  (contains "file_path" for Edit/Write)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# ── constants ────────────────────────────────────────────────────────────────

# Subprocess timeout per check (seconds).  Keep short — we're a background
# validator, not a build system.  ruff is typically <1 s; py_compile <0.5 s.
CHECK_TIMEOUT = 30

# ── helpers ───────────────────────────────────────────────────────────────────

def _read_stdin() -> dict:
    """Read and parse the PostToolUse JSON payload from stdin."""
    try:
        raw = sys.stdin.read()
        if not raw or not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def _first_line(text: str) -> str:
    """Return the first non-empty line of text, truncated to 200 chars."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:200]
    return text.strip()[:200]


def _run(cmd: list[str]) -> tuple[int, str]:
    """Run a subprocess and return (returncode, combined_output).

    Returns (1, "<timeout>") on timeout; (1, "<error>") on OSError.
    Uses UTF-8 with replacement so Windows code pages can't crash us.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=CHECK_TIMEOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        combined = (result.stderr or result.stdout or "").strip()
        return result.returncode, combined
    except subprocess.TimeoutExpired:
        return 1, f"<timeout after {CHECK_TIMEOUT}s>"
    except FileNotFoundError:
        return -1, "<tool not found on PATH>"
    except Exception as exc:
        return 1, str(exc)


# ── language validators ───────────────────────────────────────────────────────

def _validate_python(path: Path) -> tuple[bool, str]:
    """Syntax check via py_compile, then optional ruff lint.

    Returns (ok, error_message).
    """
    # 1. Syntax check — always available
    rc, out = _run([sys.executable, "-m", "py_compile", str(path)])
    if rc != 0:
        msg = out or "syntax error (py_compile failed with no output)"
        return False, msg

    # 2. Ruff lint — opportunistic; skip if not found
    rc_ruff, out_ruff = _run(["ruff", "check", "--output-format=concise", str(path)])
    if rc_ruff == -1:
        # ruff not installed — not a failure
        return True, ""
    if rc_ruff != 0 and out_ruff:
        return False, out_ruff
    return True, ""


def _validate_js(path: Path) -> tuple[bool, str]:
    """Parse-check a JS/MJS/CJS file with ``node --check``."""
    rc, out = _run(["node", "--check", str(path)])
    if rc == -1:
        # node not found — not applicable
        return True, ""
    if rc != 0:
        msg = out or "JS parse error (node --check failed with no output)"
        return False, msg
    return True, ""


# NOTE-TS: TypeScript via ``tsc --noEmit`` requires a tsconfig.json and
# resolves imports project-wide; it typically takes 5-30 s and can fail for
# reasons unrelated to the edited file (missing deps, other errors, etc.).
# Running it as a PostToolUse background hook would produce noisy false
# positives on any incomplete WIP state.  We skip TS here and note that the
# right place for full TS type-checking is a PreCommit or CI hook, not an
# edit-time background validator.
# If you have a fast single-file TS parser (e.g. ``swc``, ``@babel/parser``
# via a thin wrapper, or ``ts-node --transpile-only``), wire it in here.

def _validate_json(path: Path) -> tuple[bool, str]:
    """Validate JSON by parsing in-process — zero subprocess overhead."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        json.loads(text)
        return True, ""
    except json.JSONDecodeError as exc:
        return False, str(exc)
    except OSError as exc:
        # File vanished between Edit and our read — not our problem.
        return True, ""


# ── dispatch table ────────────────────────────────────────────────────────────

#  Maps lowercase suffix → validator callable
_VALIDATORS: dict[str, object] = {
    ".py":   _validate_python,
    ".js":   _validate_js,
    ".mjs":  _validate_js,
    ".cjs":  _validate_js,
    ".json": _validate_json,
}

# Suffixes we explicitly acknowledge but skip (see NOTE-TS).
_KNOWN_SKIP: frozenset[str] = frozenset({".ts", ".tsx", ".mts", ".cts"})


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    # ── 0. Opt-out: env var, OR a `.disabled` sentinel file (mid-session toggle) ─
    # The env var needs a session restart to take effect; the sentinel file is
    # read every invocation, so it can pause the validator during a long
    # background workflow without a restart. `del`/remove the file to re-enable.
    if os.environ.get("ASYNC_VALIDATE", "").strip().lower() == "off":
        return 0
    try:
        if (Path(__file__).resolve().parent / ".disabled").exists():
            return 0
    except Exception:
        pass

    # ── 1. Parse payload (fail-open) ──────────────────────────────────────────
    data = _read_stdin()
    if not data:
        return 0  # malformed or empty stdin → silent

    try:
        tool_name: str = str(data.get("tool_name") or "")
        tool_input = data.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            return 0

        # ── 2. Extract file path ───────────────────────────────────────────────
        file_path_raw: str = str(tool_input.get("file_path") or "")
        if not file_path_raw:
            return 0  # no file_path in payload — not applicable

        path = Path(file_path_raw)
        if not path.exists():
            return 0  # file doesn't exist yet / already deleted — skip

        # ── 3. Dispatch to language validator ────────────────────────────────
        suffix = path.suffix.lower()

        if suffix in _KNOWN_SKIP:
            # TypeScript: skip with no output (see NOTE-TS above)
            return 0

        validator = _VALIDATORS.get(suffix)
        if validator is None:
            return 0  # unknown extension — not applicable

        ok, error_msg = validator(path)  # type: ignore[operator]

        if ok:
            return 0  # success — silent

        # ── 4. Validation failed — exit 2 with concise stderr ────────────────
        first_error = _first_line(error_msg) if error_msg else "check failed (no details)"
        print(
            f"[async-validate] {path.name}: {first_error}",
            file=sys.stderr,
            flush=True,
        )
        return 2  # asyncRewake: CC wakes Claude with this stderr as system reminder

    except Exception:
        # Unexpected bug in the hook itself → fail-open, never false-alarm.
        return 0


if __name__ == "__main__":
    sys.exit(main())
