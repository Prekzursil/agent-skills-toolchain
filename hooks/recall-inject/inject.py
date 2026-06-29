#!/usr/bin/env python3
"""recall-inject/inject.py — UserPromptSubmit hook.

Reads the trigger index (built by build_index.py) and injects a terse
"Relevant memory" context block when the user's prompt strongly overlaps
with indexed note keywords.

Design contract
---------------
- FAIL-OPEN: any exception → exit 0, no output, no block.
- Never injects on every prompt (high-precision only: score ≥ MIN_SCORE,
  or a single strong token ≥ STRONG_SINGLE_LEN chars).
- Dedup per session: same note set is never injected twice in one session.
- Respects calibrated-silence gate (fail-open if hook is missing).
- Opt-out: .disabled file in this dir, or env RECALL_INJECT=off/0/false.

Output format (exit 0 + JSON to stdout when match found):
  {
    "hookSpecificOutput": {
      "hookEventName": "UserPromptSubmit",
      "additionalContext": "<formatted recall block>"
    }
  }
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

import build_index as _bi

# Re-export _tok so tests can use `inj._tok(...)`
_tok = _bi._tok

# ─── tunable constants (env-overridable) ─────────────────────────────────────
MIN_LEN = int(os.environ.get("RECALL_MIN_LEN", "15"))          # min prompt length to evaluate
MIN_SCORE = int(os.environ.get("RECALL_MIN_SCORE", "2"))       # min token overlap to qualify
STRONG_SINGLE_LEN = int(os.environ.get("RECALL_STRONG_LEN", "7"))  # single long token qualifies
MAX_NOTES = int(os.environ.get("RECALL_MAX_NOTES", "3"))       # max injected notes

# ─── generic long-word exclusion for strong-single-token path ─────────────────
# Common English words that are ≥ STRONG_SINGLE_LEN chars but far too broad to
# be a reliable solo trigger.  The strong-single-token path is reserved for
# DISTINCTIVE terms (e.g. "bromantane", "battlecats", "frida", "pwntools").
# All entries MUST be ≥ 7 chars (shorter words never reach this check).
_GENERIC_LONG: frozenset[str] = frozenset((
    "function", "database", "security", "analysis", "testing",
    "working", "problem", "project", "example", "service",
    "process", "message", "request", "response", "version",
    "address", "content", "package", "install", "running",
    "feature", "provide", "through", "without", "between",
    "another", "include", "methods", "already", "because",
    "current", "further", "looking", "reading", "writing",
    "returns", "getting", "setting", "changes", "nothing",
    "someone", "started", "stopped", "against", "created",
    "updated", "deleted", "results", "related", "backend",
    "frontend", "network", "storage", "systems", "program",
    "classes", "imports", "modules", "scripts", "sources",
    "objects", "actions", "options", "configs", "testing",
    "management", "performance", "implementation", "configure",
    "building", "creating", "handling", "executing", "checking",
    "default", "timeout", "parsing", "logging", "debugging",
    "deployment", "repository", "component", "directory",
    "existing", "following", "available", "different", "something",
    "previous", "required", "everything", "anything", "somewhere",
    "interface", "variable", "parameter", "argument", "iterator",
    "callback", "template", "language", "platform", "framework",
    "instance", "container", "resource", "workflow", "question",
    "document", "standard", "generate", "validate", "complete",
    "describe", "describe", "solution", "possible", "specific",
    "properly", "correctly", "actually", "recently", "normally",
    "directly", "returned", "resolved", "allowed", "blocked",
))

# ─── opt-out ─────────────────────────────────────────────────────────────────

_DISABLED_FILE = THIS / ".disabled"


def _disabled() -> bool:
    """Return True if this hook is disabled (fail-safe: defaults to enabled)."""
    if _DISABLED_FILE.exists():
        return True
    val = os.environ.get("RECALL_INJECT", "").strip().lower()
    return val in ("off", "0", "false")


# ─── calibrated-silence gate ──────────────────────────────────────────────────

def _cs_allow(itype: str, ctx: dict) -> bool:
    """Gate through calibrated-silence.should_interject; fail-open (True) on any error.

    ctx must be a dict (e.g. {"prompt": ..., "session_id": ...}); passing a
    string causes should_interject to crash on .get() → AttributeError.
    """
    try:
        cs_dir = THIS.parent / "calibrated-silence"
        if cs_dir.exists():
            sys.path.insert(0, str(cs_dir))
            import calibrated_silence as _c
            result = _c.should_interject(itype, ctx)
            # should_interject returns (bool, reason) or just bool
            return result[0] if isinstance(result, (tuple, list)) else bool(result)
    except Exception:
        pass
    return True  # fail-open


def _cs_record(itype: str, ctx: dict, session_id: str) -> None:
    """Record a successful interjection to calibrated-silence (best-effort)."""
    try:
        cs_dir = THIS.parent / "calibrated-silence"
        if cs_dir.exists():
            sys.path.insert(0, str(cs_dir))
            import calibrated_silence as _c
            if hasattr(_c, "record_interjection"):
                _c.record_interjection(itype, ctx, session_id)
    except Exception:
        pass


# ─── per-session dedup ────────────────────────────────────────────────────────

def _first_seen(session_id: str, sig: str) -> bool:
    """Return True if this (session, note-set signature) is NEW.

    Writes a tiny seen-file per session under the system tempdir.
    Fail-open: if anything goes wrong, returns True (allow).
    """
    try:
        safe = re.sub(r"[^a-z0-9_-]", "_", session_id.lower())[:48] or "unknown"
        seen_dir = Path(tempfile.gettempdir()) / "recall-inject"
        seen_dir.mkdir(parents=True, exist_ok=True)
        seen_file = seen_dir / f"{safe}.seen"
        seen_sigs: set[str] = set()
        if seen_file.exists():
            seen_sigs = set(seen_file.read_text(encoding="utf-8").splitlines())
        if sig in seen_sigs:
            return False
        seen_sigs.add(sig)
        seen_file.write_text("\n".join(sorted(seen_sigs)), encoding="utf-8")
        return True
    except Exception:
        return True  # fail-open


# ─── note matching ────────────────────────────────────────────────────────────

def match_notes(
    prompt: str, index: dict, min_score: int = MIN_SCORE
) -> list[dict]:
    """Return up to MAX_NOTES notes that strongly match the prompt.

    Scoring: lexical token overlap (prompt tokens ∩ note keywords).
    Qualifies if:
      - overlap count ≥ min_score, OR
      - overlap count == 1 AND the matched token is ≥ STRONG_SINGLE_LEN chars
        (catches specific technical terms like "bromantane", "calibrated").

    Returns notes sorted by descending overlap score.
    """
    prompt_toks = _tok(prompt)
    if not prompt_toks:
        return []
    notes = index.get("notes", [])
    scored: list[tuple[int, dict]] = []
    for note in notes:
        kw = set(note.get("keywords", []))
        overlap = prompt_toks & kw
        score = len(overlap)
        if score == 0:
            continue
        if score < min_score:
            # Only qualifies if there is a single DISTINCTIVE long-token match
            # (e.g. "bromantane", "battlecats", "frida") — common English words
            # like "function" or "database" that happen to be ≥ STRONG_SINGLE_LEN
            # chars must NOT fire on their own; they are in _GENERIC_LONG.
            if not any(
                len(t) >= STRONG_SINGLE_LEN and t not in _GENERIC_LONG
                for t in overlap
            ):
                continue
        scored.append((score, note))
    # Sort by score descending; stable secondary sort by title for determinism
    scored.sort(key=lambda x: (-x[0], x[1].get("title", "")))
    return [n for _, n in scored[:MAX_NOTES]]


# ─── message formatting ───────────────────────────────────────────────────────

def format_message(matches: list[dict]) -> str:
    """Format matched notes as a terse additionalContext block."""
    lines = ["[recall-inject] Relevant memory:"]
    for note in matches:
        title = note.get("title", "")
        summary = note.get("summary", "")
        permalink = note.get("permalink", "")
        if permalink:
            line = f"- {title} — {summary} (recall via basic-memory read_note '{permalink}')"
        else:
            line = f"- {title} — {summary}"
        lines.append(line)
    return "\n".join(lines)


# ─── main run logic ───────────────────────────────────────────────────────────

def run(
    data: dict,
    vault_dirs: list[Path] | None = None,
    memory_md_paths: list[Path] | None = None,
    index_path: Path | None = None,
) -> tuple[int, str | None]:
    """Core hook logic. Returns (exit_code, message_or_None).

    Always returns exit code 0 (inject-only, never block).
    Returns None for the message if no injection is warranted.
    Never raises.
    """
    try:
        if _disabled():
            return 0, None

        prompt = str(data.get("prompt", ""))
        if len(prompt.strip()) < MIN_LEN:
            return 0, None

        session_id = str(data.get("session_id", ""))

        # Resolve defaults through _bi so tests can monkeypatch them
        resolved_vault_dirs = vault_dirs if vault_dirs is not None else _bi.find_vault_dirs()
        resolved_memory_md = memory_md_paths if memory_md_paths is not None else _bi.find_memory_md_paths()
        resolved_index_path = index_path if index_path is not None else _bi.INDEX_PATH

        # Load/build the index
        index = _bi.get_or_build_index(
            resolved_vault_dirs, resolved_memory_md, resolved_index_path
        )
        if not index.get("notes"):
            return 0, None

        # Match notes
        matches = match_notes(prompt, index)
        if not matches:
            return 0, None

        # Calibrated-silence gate (fail-open).
        # ctx must be a dict — passing a string causes should_interject to crash
        # on context.get("ledger_path") → AttributeError → spurious fail-open True.
        _cs_ctx = {"prompt": prompt[:200], "session_id": session_id}
        if not _cs_allow("gem", _cs_ctx):
            return 0, None

        # Per-session dedup: compute a stable signature for this note set
        sig = hashlib.md5(
            "|".join(sorted(n["title"] for n in matches)).encode("utf-8")
        ).hexdigest()[:12]
        if not _first_seen(session_id, sig):
            return 0, None

        msg = format_message(matches)
        _cs_record("gem", _cs_ctx, session_id)
        return 0, msg

    except Exception:
        return 0, None  # fail-open: any error → silent exit 0


# ─── hook entry point ─────────────────────────────────────────────────────────

def main() -> int:
    """UserPromptSubmit hook entry point.

    Reads JSON from stdin, emits JSON to stdout if a recall injection is
    warranted, then exits 0. Always exits 0 (fail-open).
    """
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    try:
        code, msg = run(data)
        if msg:
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": msg,
                }
            }))
        return code
    except Exception:
        return 0  # fail-open


if __name__ == "__main__":
    sys.exit(main())
