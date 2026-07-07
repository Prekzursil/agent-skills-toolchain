#!/usr/bin/env python3
"""test-tamper-guard/guard.py — PreToolUse hook: EvilGenie diff-guard.

Intercepts `git commit` Bash calls and scans staged test-file diffs for
weakening signals (deleted assertions, added skips, trivial-true stubs,
whole-file deletions). If any signal fires it emits an additionalContext
warning (exit 0) and logs a `failure` to the event ledger.

MODE GATE (TEST_TAMPER_MODE env var): "warn" (default) | "block".
  - "warn" (default): EXACTLY the original behaviour — every signal warns,
    exit 0, never blocks.
  - "block": the three HIGH-CONFIDENCE signals (file_deleted, assertion_net_drop,
    skip_added) exit 2 to BLOCK the commit; trivial_assert_added stays a warn
    (higher false-positive risk). Opt-in only — the default is unchanged.

FAIL-OPEN: every code path is wrapped in try/except.  Any exception →
exit 0, no output.  A crashing hook is worse than a silent one.

NON-NAGGING: only emits output when a concrete tamper signal is found.

EXTERNAL-ANCHORED: decisions come from `git diff --cached` output, which
the model cannot retroactively alter from within the hook.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Mode gate (G2)
# ---------------------------------------------------------------------------
# Default "warn" reproduces the original hook EXACTLY. "block" is strictly opt-in.
MODE = os.environ.get("TEST_TAMPER_MODE", "warn").lower()

# Only the HIGH-CONFIDENCE signals block under TEST_TAMPER_MODE=block. These are
# externally anchored to a real `git diff --cached` and have very low false-positive
# risk. `trivial_assert_added` is deliberately EXCLUDED — a real `assert True`
# (e.g. a placeholder in a genuinely-new scaffold) is more likely benign, so it
# stays a warn even in block mode.
_BLOCK_SIGNALS: frozenset[str] = frozenset(
    {"file_deleted", "assertion_net_drop", "skip_added"}
)

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# File-name patterns that identify test files.
_TEST_FILE_PATS: list[re.Pattern] = [
    re.compile(r"(^|[\\/])__tests__[\\/]", re.IGNORECASE),
    re.compile(r"(^|[\\/])tests?[\\/]", re.IGNORECASE),
    re.compile(r"(^|[\\/])specs?[\\/]", re.IGNORECASE),
    re.compile(r"test[_.-]", re.IGNORECASE),
    re.compile(r"[_.-]test\b", re.IGNORECASE),
    re.compile(r"\.test\.", re.IGNORECASE),
    re.compile(r"\.spec\.", re.IGNORECASE),
    re.compile(r"(^|[\\/])conftest\.py$", re.IGNORECASE),
    re.compile(r"(^|[\\/])test_[^/]+\.py$", re.IGNORECASE),
    re.compile(r"[^/]+_test\.go$", re.IGNORECASE),
    re.compile(r"(^|[\\/])Test[A-Z][^/]*\.(java|kt|cs|cpp|cc)$"),
    re.compile(r"\bspec\b", re.IGNORECASE),
]

# Lines that indicate assertion presence (removed lines are suspicious).
_ASSERT_RE = re.compile(
    r"\b(assert|expect|should|EXPECT_|ASSERT_|assertThat|assertEqual|"
    r"assertTrue|assertFalse|assertRaises|assertIn|assertIs|assertEquals|"
    r"assertNotEqual|assertGreater|assertLess|verify|must\b|require\.)",
    re.IGNORECASE,
)

# Added-line patterns that indicate test disabling / weakening.
_SKIP_RE = re.compile(
    r"(@pytest\.mark\.skip|@pytest\.mark\.xfail|"
    r"\.skip\s*\(|\.only\s*\(|"
    r"\bxit\s*\(|\bxdescribe\s*\(|"
    r"\bit\.skip\b|\btest\.skip\b|"
    r"\bdescribe\.skip\b|\bcontext\.skip\b|"
    r"\bt\.Skip\s*\(|"
    r"@Disabled\b|@Ignore\b|"
    r"\[Ignore\]|\[Skip\]|"
    r"# type: ignore.*assert|"
    r"\bpending\s*\(\s*\)|"
    r"TODO.*test|FIXME.*test)",
    re.IGNORECASE,
)

# Added-line patterns that are trivially-true no-op asserts.
_TRIVIAL_ASSERT_RE = re.compile(
    r"(assert\s+True\b|assert\s+1\b|assert\s+not\s+False\b|"
    r"expect\s*\(\s*true\s*\)|assertTrue\s*\(\s*true\s*\)|"
    r"assertFalse\s*\(\s*false\s*\)|"
    r"ASSERT_TRUE\s*\(\s*true\s*\)|EXPECT_TRUE\s*\(\s*true\s*\))",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_test_file(path: str) -> bool:
    return any(p.search(path) for p in _TEST_FILE_PATS)


def _run(args: list[str], cwd: str) -> str:
    """Run a subprocess and return stdout as UTF-8. Raises on error."""
    result = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )
    return result.stdout


def _log_failure(cwd: str, message: str, preconditions: str) -> None:
    """Call note.py to log a failure to the event ledger. Fail-open."""
    try:
        note_py = str(
            Path(__file__).resolve().parent.parent / "event-ledger" / "note.py"
        )
        if not Path(note_py).exists():
            return
        subprocess.run(
            [
                sys.executable,
                note_py,
                "--kind",
                "failure",
                message,
                "--preconditions",
                preconditions,
                "--cwd",
                cwd,
            ],
            timeout=10,
            encoding="utf-8",
            errors="replace",
            capture_output=True,  # don't leak note.py output
        )
    except Exception:
        pass  # fail-open: ledger logging is best-effort


def _analyse_diff(diff_text: str) -> dict:
    """Scan a single file's diff for weakening signals.

    Returns a dict: {signal_name: [sample_line, ...]}
    """
    signals: dict[str, list[str]] = {}

    removed_assert_count = 0
    added_assert_count = 0

    for raw_line in diff_text.splitlines():
        # Skip diff header lines (@@, ---, +++)
        if (
            raw_line.startswith("---")
            or raw_line.startswith("+++")
            or raw_line.startswith("@@")
        ):
            continue

        if raw_line.startswith("-"):
            content = raw_line[1:]
            stripped = content.strip()
            if not stripped:
                continue
            # Count removed assertions
            if _ASSERT_RE.search(content):
                removed_assert_count += 1

        elif raw_line.startswith("+"):
            content = raw_line[1:]
            stripped = content.strip()
            if not stripped:
                continue
            # Skip/disable patterns on added lines
            if _SKIP_RE.search(content):
                signals.setdefault("skip_added", []).append(stripped[:120])
            # Trivial-true asserts on added lines
            if _TRIVIAL_ASSERT_RE.search(content):
                signals.setdefault("trivial_assert_added", []).append(stripped[:120])
            # Count added assertions (for net-drop calc)
            if _ASSERT_RE.search(content):
                added_assert_count += 1

    # Net assertion drop
    net_drop = removed_assert_count - added_assert_count
    if net_drop > 0:
        signals["assertion_net_drop"] = [
            f"removed {removed_assert_count} assert-lines, added {added_assert_count} "
            f"(net drop: {net_drop})"
        ]

    return signals


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    try:
        raw = sys.stdin.read() or "{}"
        data = json.loads(raw)
    except Exception:
        return 0  # fail-open: malformed stdin → do nothing

    try:
        tool_input = data.get("tool_input") or {}
        command = str(tool_input.get("command") or "")

        # Only act on git commit commands.
        if not re.search(r"\bgit\b.*\bcommit\b", command):
            return 0

        # Determine cwd for git operations.
        cwd = str(data.get("cwd") or os.getcwd())

        # --- 1. Find staged files -----------------------------------------
        try:
            name_status = _run(["git", "diff", "--cached", "--name-status"], cwd)
        except Exception:
            return 0  # not a git repo or git not available → silent

        # Parse: each line is "<STATUS>\t<path>"  (D = deleted, M = modified, A = added, R = renamed)
        staged_test_files: dict[str, str] = {}  # path → status
        for line in name_status.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 2)
            if len(parts) < 2:
                continue
            status = parts[0].strip()
            # Renames: "R\told\tnew" — check both paths
            paths_to_check = parts[1:]
            for p in paths_to_check:
                if _is_test_file(p):
                    staged_test_files[p] = status
                    break  # one match per diff line is enough

        if not staged_test_files:
            return 0  # no test files staged → silent

        # --- 2. Analyse each staged test file --------------------------------
        findings: list[str] = []
        seen_signals: set[str] = set()

        for filepath, status in staged_test_files.items():
            file_signals: dict[str, list[str]] = {}

            if status.startswith("D"):
                # Whole file deleted — unconditionally flag it.
                file_signals["file_deleted"] = [f"{filepath} staged for deletion"]
            else:
                # Get the diff and scan it.
                try:
                    diff = _run(["git", "diff", "--cached", "--", filepath], cwd)
                except Exception:
                    continue  # can't get diff for this file → skip
                if diff:
                    file_signals = _analyse_diff(diff)

            if file_signals:
                seen_signals.update(file_signals)
                sig_parts = []
                for sig_name, samples in file_signals.items():
                    label = sig_name.replace("_", " ")
                    sig_parts.append(f"  [{label}]: {samples[0]}")
                    for s in samples[1:3]:  # at most 3 examples per signal
                        sig_parts.append(f"    also: {s}")
                findings.append(f"- {filepath}:\n" + "\n".join(sig_parts))

                # Log each file+signal combo to the event ledger.
                for sig_name in file_signals:
                    preconditions = f"test-tamper:{filepath}:{sig_name}"
                    msg = (
                        f"EvilGenie guard: staged test weakening detected — "
                        f"{filepath} ({sig_name})"
                    )
                    _log_failure(cwd, msg, preconditions)

        # --- 3. Emit warning (or, in block mode, BLOCK) if any findings ------
        if findings:
            body = "\n".join(findings)

            # G2 — block mode: if any HIGH-CONFIDENCE signal fired, exit 2 to block
            # the commit. trivial_assert_added alone never blocks. warn mode (default)
            # and low-confidence-only findings fall through to the exit-0 warning.
            if MODE == "block" and (seen_signals & _BLOCK_SIGNALS):
                blocked = sorted(seen_signals & _BLOCK_SIGNALS)
                sys.stderr.write(
                    "EvilGenie TDD-guard BLOCK (TEST_TAMPER_MODE=block): staged test "
                    "file(s) show high-confidence weakening signal(s) "
                    f"[{', '.join(blocked)}]. Commit blocked.\n\n"
                    + body
                    + "\n\nFix the source code instead of the tests, or unstage the "
                    "weakening change. If this is genuinely intentional, set "
                    "TEST_TAMPER_MODE=warn for this commit.\n"
                )
                return 2

            warning = (
                "EvilGenie TDD-guard WARNING: staged test file(s) show weakening signals "
                "that may indicate test gaming rather than genuine fixes.\n\n"
                + body
                + "\n\nIf these changes are intentional, document the reason "
                "in the commit message.  If not, fix the source code instead of the tests."
            )
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "additionalContext": warning,
                        }
                    }
                )
            )

    except Exception:
        pass  # fail-open: any unhandled exception → exit 0, no output

    return 0


if __name__ == "__main__":
    sys.exit(main())
