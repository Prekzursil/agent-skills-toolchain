#!/usr/bin/env python3
"""journey-coverage — every declared user-journey must be RUN before "done".

A Stop hook (the third functional-acceptance gem, after claim-guard G1 +
test-tamper-guard G2). Where claim-guard asks "does this 'it works' claim have ANY
e2e evidence?", this asks the COMPLETENESS question: when the final message claims
the app is done/ready/shippable, was EVERY held-out user-journey / E2E spec in the
repo actually exercised THIS turn? A journey that exists but was never run is the
classic green-but-broken blind spot — the golden-journey that nobody executed.

External signals (neither authored by the model in-context):
  1. the set of journey/E2E spec FILES on disk (a fact of the repo), and
  2. the claim-guard Bash-exit ledger (the ok=true commands run THIS turn).
A journey is "covered" iff an ok=true command this turn ran it (by path/basename) or
was a broad e2e runner (playwright/cypress/`npm run e2e`/vitest/jest e2e) that runs
all specs. On a "done" claim with uncovered journeys, inject a warning naming them.

Modes (JOURNEY_COVERAGE_MODE): "warn" (default) | "off" | "block". Block exits 2
ONLY for a done-claim with uncovered journeys; warn/off never block. FAIL-OPEN:
any exception -> silent exit 0 (a crashing gate is worse than a silent one). Silent
when there are no journey specs, no done-claim, or every journey was covered.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

MODE = os.environ.get("JOURNEY_COVERAGE_MODE", "warn").lower()

# The claim-guard ledger (shared signal): {ts,cmd,exit,ok} per Bash call this turn.
_LEDGER_ROOT = Path(
    os.environ.get(
        "CLAIM_GUARD_LEDGER_ROOT",
        str(Path(tempfile.gettempdir()) / "claude-claim-ledger"),
    )
)

# A "done / ready to ship" claim about the app as a whole (assertive, not hedged).
_DONE = re.compile(
    r"\b(?:"
    r"(?:the\s+)?app\s+(?:is\s+)?(?:done|ready|working|shippable|ships?|shipped)"
    r"|ready\s+to\s+(?:ship|release|merge)"
    r"|(?:it'?s|this\s+is)\s+(?:done|ready|shippable|production[-\s]ready)"
    r"|(?:feature|release|v?\d[\d.]*)\s+is\s+(?:done|ready|complete|shippable)"
    r"|everything\s+works\s+end[-\s]to[-\s]end"
    r")\b",
    re.IGNORECASE,
)
# Hedges within +/-120 chars suppress the claim (mirrors claim-guard).
_HEDGE = re.compile(
    r"\b(?:should|would|expect(?:ed)?|once\s+you|after\s+you|if\s+you|"
    r"not\s+(?:yet|quite)|almost|nearly|todo|hopefully|might|may|could)\b",
    re.IGNORECASE,
)

# Journey / E2E spec file signatures (path globs, case-insensitive on basename).
_SPEC_GLOBS = (
    "**/*golden*journey*.spec.*",
    "**/*golden-journey*.spec.*",
    "**/e2e/**/*.spec.*",
    "**/e2e/**/*.test.*",
    "**/*.e2e.spec.*",
    "**/*.e2e.test.*",
    "**/*journey*.spec.*",
    "**/cypress/e2e/**/*.cy.*",
    "**/tests/e2e/**/*.py",
    "**/playwright/**/*.spec.*",
)
# A command that runs ALL specs (so it covers every journey) even without naming one.
_BROAD_E2E = re.compile(
    r"\b(?:playwright\s+test|cypress\s+run|npm\s+run\s+e2e|pnpm\s+e2e|yarn\s+e2e|"
    r"npx\s+playwright|vitest\s+run.*e2e|jest.*e2e|pytest\s+-m\s+e2e|nightwatch)\b",
    re.IGNORECASE,
)
# Dirs never worth scanning for journeys.
_SKIP_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "out",
    "build",
    "coverage",
    ".venv",
    "venv",
}


def is_done_claim(text: str) -> bool:
    """True iff the text makes an assertive (non-hedged) app-is-done claim."""
    if not text:
        return False
    for m in _DONE.finditer(text):
        lo = max(0, m.start() - 120)
        hi = min(len(text), m.end() + 120)
        if not _HEDGE.search(text[lo:hi]):
            return True
    return False


def find_journey_specs(root: str) -> list[str]:
    """All journey/E2E spec files under ``root`` (repo-relative POSIX paths, sorted)."""
    base = Path(root)
    found: set[str] = set()
    for pattern in _SPEC_GLOBS:
        for p in base.glob(pattern):
            if not p.is_file():
                continue
            if any(part in _SKIP_DIRS for part in p.parts):
                continue
            found.add(p.relative_to(base).as_posix())
    return sorted(found)


def _names(cmd: str, spec_rel: str) -> bool:
    """True iff ``cmd`` targets this specific spec (full rel path, basename, or stem)."""
    base = Path(spec_rel).name
    stem = base.split(".")[0]
    return spec_rel in cmd or base in cmd or (len(stem) >= 4 and stem in cmd)


def uncovered_journeys(specs: list[str], ok_cmds: list[str]) -> list[str]:
    """Journeys with NO ok=true run this turn (pure — the testable core).

    Per command: one that NAMES specific spec(s) covers only those; a BROAD e2e
    runner that names none (a bare all-specs run) covers every journey. So a
    targeted ``playwright test <spec>`` never masks the OTHER journeys, while a
    bare ``playwright test`` / ``npm run e2e`` covers the whole set.
    """
    covered: set[str] = set()
    for cmd in ok_cmds:
        named = [s for s in specs if _names(cmd, s)]
        if named:
            covered.update(named)
        elif _BROAD_E2E.search(cmd):
            covered.update(specs)
    return [s for s in specs if s not in covered]


def _ok_commands(session_id: str) -> list[str]:
    """The ok=true Bash commands recorded this turn (claim-guard ledger)."""
    ledger = _LEDGER_ROOT / f"{_safe(session_id)}.ndjson"
    cmds: list[str] = []
    try:
        with open(ledger, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("ok") and isinstance(rec.get("cmd"), str):
                    cmds.append(rec["cmd"])
    except OSError:
        return []
    return cmds


def _safe(session_id: str) -> str:
    return (
        "".join(c if c.isalnum() or c in "-_." else "-" for c in str(session_id))[:80]
        or "unknown"
    )


def _final_text(transcript_path: str) -> str:
    """Concatenated text of the final assistant message in the transcript JSONL."""
    try:
        last = ""
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("type") == "assistant" or rec.get("role") == "assistant":
                    msg = rec.get("message", rec)
                    content = msg.get("content") if isinstance(msg, dict) else None
                    parts: list[str] = []
                    if isinstance(content, str):
                        parts.append(content)
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                parts.append(str(block.get("text") or ""))
                            elif isinstance(block, str):
                                parts.append(block)
                    if parts:
                        last = "\n".join(parts)
        return last
    except OSError:
        return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if MODE == "off":
        return 0
    try:
        if payload.get("stop_hook_active"):
            return 0
        cwd = payload.get("cwd") or os.getcwd()
        text = _final_text(payload.get("transcript_path", ""))
        if not is_done_claim(text):
            return 0
        specs = find_journey_specs(cwd)
        if not specs:
            return 0  # not an app with declared journeys — nothing to gate
        ok_cmds = _ok_commands(payload.get("session_id", ""))
        missing = uncovered_journeys(specs, ok_cmds)
        if not missing:
            return 0  # every journey was exercised this turn — silent
        shown = ", ".join(missing[:8]) + (" …" if len(missing) > 8 else "")
        msg = (
            f"JOURNEY-COVERAGE: an app-is-done claim, but {len(missing)} declared "
            f"user-journey/E2E spec(s) were NOT run this turn: {shown}. A journey that "
            "exists but was never executed is the classic green-but-broken blind spot. "
            "Run them (and show the real artifact) before calling the app done."
        )
        # Emit the inject-only JSON in EVERY firing mode, block included. This hook is
        # registered through _dispatch/manifest.json, and that dispatcher aggregates
        # stdout additionalContext while discarding the return code — so a block-mode
        # finding that only wrote stderr + `return 2` reached nobody: exit 2 was
        # dropped and the model never saw the message. Standalone, Claude Code ignores
        # stdout when a hook exits 2 and uses stderr, so printing here is inert there
        # and load-bearing under the dispatcher.
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
        if MODE == "block":
            sys.stderr.write(msg + "\n")
            return 2
        return 0
    except Exception:  # noqa: BLE001 - fail-open: a crashing gate is worse than none
        return 0


if __name__ == "__main__":
    sys.exit(main())
