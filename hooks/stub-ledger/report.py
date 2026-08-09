#!/usr/bin/env python3
r"""stub-ledger/report.py — Stop hook. Surfaces still-open placeholders.

Reads the per-session ledger written by record.py, RE-SCANS each recorded file's
CURRENT content, and surfaces only the stubs that are STILL present (resolved ones
and deleted files drop out automatically — honest "still open"). Injects:
"N stub(s)/TODO(s) introduced this session still open: <list>".

NON-DUPLICATIVE vs B1 dark-surface (deliberate complement):
  - dark-surface fires on  COMPLETION-CLAIM + stub-in-edited-file.
  - report.py fires on  NO completion claim + still-open stub  (the silently-forgotten
    case dark-surface cannot see). It uses dark-surface's EXACT completion regex, so
    the two partition the space with no overlap. Set STUB_LEDGER_ALWAYS=1 to surface
    the full list regardless of claim (then it intentionally overlaps — off by default).

FAIL-OPEN (try/except -> exit 0). Anti-loop via stop_hook_active. Inject-only.
Opt-out: STUB_LEDGER=off in env, or a hooks/stub-ledger/.disabled file.

settings.json (Stop, no matcher):
  {"type":"command",
   "command":"python C:/Users/Prekzursil/.claude/hooks/stub-ledger/report.py",
   "timeout":10,"statusMessage":"Stub-ledger: surfacing open placeholders"}
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
if str(THIS) not in sys.path:
    sys.path.insert(0, str(THIS))

DISABLED = THIS / ".disabled"
LEDGER_ROOT = Path(
    os.environ.get("STUB_LEDGER_ROOT", str(Path.home() / ".claude" / "stub-ledger"))
)

# EXACT mirror of dark-surface's completion regex -> clean complementary partition.
_COMPLETION = re.compile(
    r"\b(?:implemented|wired (?:it |them |this )?(?:up|in)|fully (?:wired|functional|implemented)|"
    r"now (?:works|functional)|plug-and-play|ready to (?:use|go)|feature is (?:complete|done)|"
    r"is (?:now )?(?:complete|implemented|wired|functional)|shipped (?:it|the))\b",
    re.IGNORECASE,
)


def _real_completion_claim(text: str) -> bool:
    """True if the final message ASSERTS completion, False if it merely quotes the phrase.

    `_COMPLETION.search()` alone reads any occurrence as an assertion, so a message *explaining*
    the guard -- quoting `is now complete` while describing what suppresses the ledger -- silences
    the ledger it is describing. That is the use-vs-mention defect, and this surface is the one
    open loop b788a392 names: a matcher fix confined to stubscan.py never reaches the final-MESSAGE
    path, because report.py compiles its own pattern and only late-imports stubscan.

    Routed through the shared discriminator with kind="claim" (NOT "marker"): a completion claim is
    real in ordinary prose and a mention when fenced or backticked -- the opposite polarity to a
    TODO marker. Fail-open: if the discriminator cannot be imported, behaviour is exactly the
    previous regex, so a broken import can never silently disarm the guard.
    """
    m = _COMPLETION.search(text)
    if not m:
        return False
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
        from use_vs_mention import Context, is_real_occurrence
    except Exception:
        return True  # fail-open: preserve the pre-existing regex behaviour
    ctx = Context(source="assistant_message")
    return any(
        is_real_occurrence(text, (mm.start(), mm.end()), ctx, kind="claim")
        for mm in _COMPLETION.finditer(text)
    )


def _ledger_file(session_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in str(session_id))[
        :80
    ]
    return LEDGER_ROOT / f"{safe or 'unknown'}.ndjson"


# See journey-coverage/check.py for the measurement that fixes this budget (turn-size p50
# 28-63 KB, p90 ~450 KB; this check's target record sat 6,436 bytes from EOF in a 114 MB file).
_TAIL_BYTES = 8 * 1024 * 1024


def _tail_lines(transcript_path: str):
    """Backward (newest-first) line iterator from the shared bounded reader, or None."""
    try:
        shared = str(Path(__file__).resolve().parent.parent / "_shared")
        if shared not in sys.path:
            sys.path.insert(0, shared)
        from transcript_tail import iter_tail_lines
    except Exception:
        return None
    return iter_tail_lines(transcript_path, max_bytes=_TAIL_BYTES)


def _parts(ev: dict) -> list[str]:
    """Text parts of ONE record — the unchanged per-record body of the original scan.

    NOTE this predicate is NOT interchangeable with journey-coverage's or with
    `transcript_tail.final_assistant_text`: it requires `msg["role"] == "assistant"` (the
    others do not), ignores bare-string content blocks (journey-coverage keeps them), and
    joins with " " (journey-coverage "\\n", `final_assistant_text` ""). Swapping in the shared
    helper wholesale would silently change what this gate reads, so only the IO is shared.
    """
    msg = (
        ev.get("message")
        if ev.get("type") == "assistant"
        else (ev if ev.get("role") == "assistant" else None)
    )
    if not (isinstance(msg, dict) and msg.get("role") == "assistant"):
        return []
    c = msg.get("content") or []
    if isinstance(c, list):
        return [
            str(b.get("text") or "")
            for b in c
            if isinstance(b, dict) and b.get("type") == "text"
        ]
    if isinstance(c, str):
        return [c]
    return []


def _final_text_forward(transcript_path: str) -> tuple[str, bool]:
    """The original O(session-length) scan. Retained as the EXACTNESS fallback."""
    p = Path(transcript_path)
    if not p.exists():
        return "", False
    last = ""
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if not isinstance(ev, dict):
                    continue
                parts = _parts(ev)
                if parts:
                    last = " ".join(parts)
    except Exception:
        return "", False
    return last, True


def _final_text(transcript_path: str) -> tuple[str, bool]:
    """(text, ok) — final assistant message. O(tail), not O(session length).

    The forward scan settles on the LAST record with text parts; from EOF the FIRST such
    record is that same record, so the result is byte-identical BY CONSTRUCTION rather than
    by luck. `ok=False` means the transcript could not be read at all — under P2-01 that is
    NOT-CHECKED, not "no completion claim", because the two used to be indistinguishable and
    the second silently SUPPRESSES this gate (main() defers to dark-surface on a claim).
    """
    for line in _tail_lines(transcript_path) or ():
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if not isinstance(ev, dict):
            continue
        parts = _parts(ev)
        if parts:
            return " ".join(parts), True
    return _final_text_forward(transcript_path)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _deferred() -> list[tuple[str, str]]:
    """Explicitly-deferred false positives from LEDGER_ROOT/.deferred.

    One rule per line, `#` comments ignored:  ``[file-substr::]needle``
    Returns (file_substr, needle) pairs, both normalized; an empty file_substr
    matches any file. Missing/unreadable file -> no rules (fail-open).
    """
    try:
        raw = (LEDGER_ROOT / ".deferred").read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    rules: list[tuple[str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fsub, sep, needle = line.partition("::")
        if not sep:
            fsub, needle = "", line
        needle = _norm(needle)
        if needle:
            rules.append((_norm(fsub).replace("\\", "/"), needle))
    return rules


def _is_deferred(fp: str, snippet: str, rules: list[tuple[str, str]]) -> bool:
    """Case-insensitive substring match on the already-normalized snippet."""
    f = _norm(fp).replace("\\", "/")
    return any((not fsub or fsub in f) and needle in snippet for fsub, needle in rules)


def _load_ledger(session_id: str) -> list[dict]:
    f = _ledger_file(session_id)
    if not f.exists():
        return []
    recs = []
    try:
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return []
    return recs


def still_open(session_id: str) -> list[tuple[str, str, str]]:
    """Return (file, marker, snippet) for ledger stubs STILL detected in the current file.

    Correctness note: we RE-RUN the same detector (stubscan.find_stubs) on each file's
    current content and keep a recorded stub only if its exact normalized snippet is
    still emitted. A plain substring check is WRONG for pass-only bodies — the `def foo():`
    header survives after the body is implemented, so it would falsely report "still open".
    When the file is unknown/unreadable (e.g. an unsaved path) we keep the record, since we
    cannot prove it was resolved.
    """
    import stubscan

    DELETED, UNREADABLE = object(), object()
    recs = _load_ledger(session_id)
    if not recs:
        return []
    deferred_rules = _deferred()
    cur: dict[str, object] = {}  # file -> set(current snippets) | DELETED | UNREADABLE
    out: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for r in recs:
        fp = str(r.get("file") or "")
        if fp and stubscan.is_test_file(fp):
            continue  # test/fixture files legitimately contain stub/TODO markers
        snippet = _norm(str(r.get("snippet") or ""))
        marker = str(r.get("marker") or "stub")
        if not snippet:
            continue
        if _is_deferred(fp, snippet, deferred_rules):
            continue  # verified false positive, recorded in .deferred
        if fp and fp not in cur:
            try:
                if Path(fp).exists():
                    body = Path(fp).read_text(encoding="utf-8", errors="replace")
                    # Pass the path: it lets stubscan route candidates through the shared
                    # use-vs-mention discriminator, so prose ABOUT stubs in a design doc is
                    # not re-scored as unfinished work (loop 6f8a224e, 9/9 measured fires).
                    cur[fp] = {
                        _norm(sn) for (_mk, _ln, sn) in stubscan.find_stubs(body, fp)
                    }
                else:
                    cur[fp] = DELETED
            except Exception:
                cur[fp] = UNREADABLE
        if fp:
            state = cur.get(fp)
            if state is DELETED:
                continue  # file gone -> stub gone
            if isinstance(state, set) and snippet not in state:
                continue  # detector no longer flags it -> resolved
            # UNREADABLE -> keep (cannot prove it was resolved)
        key = (fp, snippet)
        if key in seen:
            continue
        seen.add(key)
        out.append((fp, marker, snippet))
    return out


def main() -> int:
    try:
        if DISABLED.exists() or os.environ.get("STUB_LEDGER", "").lower() in (
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
        session_id = str(data.get("session_id") or "unknown")
        always = os.environ.get("STUB_LEDGER_ALWAYS", "").lower() in ("1", "true", "on")
        if not always:
            tp = str(data.get("transcript_path") or "")
            text, ok = _final_text(tp)
            if tp and not ok:
                # TYPED SILENCE (P2-01). An unreadable transcript used to read as "no
                # completion claim", which does NOT suppress this gate — so it would go on
                # to report stubs while unable to check whether dark-surface owns the turn.
                # Say so instead of pretending the claim surface was examined.
                print(
                    json.dumps(
                        {
                            "hookSpecificOutput": {
                                "hookEventName": "Stop",
                                "additionalContext": (
                                    "[stub-ledger] NOT-CHECKED: the transcript could not be "
                                    "read, so the completion-claim surface that decides "
                                    "whether this gate defers to dark-surface was not "
                                    "examined. This silence is NOT a pass."
                                ),
                            }
                        }
                    )
                )
                return 0
            if text and _real_completion_claim(text):
                return 0  # completion claim present -> defer to dark-surface

        open_stubs = still_open(session_id)
        if not open_stubs:
            return 0

        def _short(fp: str) -> str:
            return os.path.basename(fp) if fp else "(unsaved)"

        shown = "; ".join(
            f"{_short(fp)}:{mk} — {sn[:50]}" for fp, mk, sn in open_stubs[:6]
        )
        more = f" (+{len(open_stubs) - 6} more)" if len(open_stubs) > 6 else ""
        msg = (
            f"[stub-ledger] {len(open_stubs)} placeholder/TODO(s) you introduced this "
            f"session are STILL open and were not surfaced by a completion claim: {shown}{more}. "
            f"Finish, wire, or explicitly defer them (say so) before considering this work done "
            f"— built-but-incomplete code should not be silently forgotten."
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
