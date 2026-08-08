#!/usr/bin/env python
"""Stop hook — dark-surface / stub detector (deterministic nudge variant).

Fixes the #1 mined recurring failure GREEN-not-LIVE: a "done/implemented/wired" claim while the code
added this session is actually a stub / placeholder / unimplemented surface. When the final assistant
message contains a COMPLETION claim AND a source file edited THIS SESSION still contains a stub marker,
inject a one-shot nudge to verify the feature is actually wired (not a stub) — green tests pass over a
dark surface. Deterministic (no model call); inject only; never blocks; fail-open; anti-loop.

A6 SHADOW GATE (DARK_SURFACE_MODE env var): "shadow" (default) | anything else.
  - "shadow" (DEFAULT — A6 wire-dormant-gates): OBSERVE-ONLY. The would-have-fired verdict is recorded
    to the SI-2 shadow sink and surfaced as a clearly-labelled ``[SHADOW]`` note (this gate never
    blocked, so shadow only relabels + logs). This is the mode the session-new
    ``_dispatch/manifest.json`` runs it under.
  - any other value (e.g. "live"): the original plain (non-shadow) nudge, no sink write.

Reuses edit-validate's per-session {sid}.edits list + claim-check's transcript-parse pattern.
Opt-out:  DARK_SURFACE=off  in env, or  hooks/dark-surface/.disabled

USE-vs-MENTION (wired 2026-08-08). Both regexes are payload matchers, so both false-fired.
They are now routed through ``hooks/_shared/use_vs_mention.py`` with DIFFERENT kinds,
because they ask opposite questions and share a kind would invert one of them:

  * ``STUB_RE`` over an edited file body -> ``kind="stub"``. Identical contract to
    ``stub-ledger`` ("built-but-incomplete CODE must not be silently forgotten"), which is
    already wired to that kind. All SIX recorded fires (2026-08-08:
    ``_bp_data_4.py`` / ``use_vs_mention.py`` `placeholder`,
    ``_defer_stub_fixtures.py`` `NotImplementedError`, and ``_uvm_corpus_extend.py`` /
    ``_uvm_append_tests.py`` / ``_uvm_bothstates_bool.py`` `# TODO`) are markers spelled
    inside STRING LITERALS -- corpus data and code templates, not pending work. Measured
    35 raw matches -> 0 survivors, every one ``stub:string-literal`` bar one
    ``stub:inline-code-span``.
  * ``COMPLETION_RE`` over the final assistant message -> ``kind="claim"``, NOT ``marker``.
    This is the polarity trap the ``doclink`` inversion already proves is easy to get
    backwards: ``_is_prose()`` returns True for ``source="assistant_message"``, so marker
    semantics would return MENTION for every claim written in ordinary prose and DISARM
    the gate entirely. ``claim`` inverts that -- a claim asserted in prose is REAL, and is
    a MENTION only when fenced or in an inline code span (i.e. when the message is quoting
    the phrase, such as this docstring being pasted into a report).

FAIL-OPEN: a missing or raising discriminator leaves behaviour EXACTLY as before.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

THIS = Path(__file__).resolve().parent

# A6 shadow gate (SI-2). Heuristic tier ⇒ SHADOW by default (SI-2 DEFAULT_MODE_BY_TIER).
DARK_SURFACE_MODE = os.environ.get("DARK_SURFACE_MODE", "shadow").lower()

# Anti-zombie CONTRACT (SI-2): a falsifiable fire-rate hypothesis + owner + review
# deadline so the F1 scorer / native Cron can retire this gate if it never earns a
# promotion out of shadow.
CONTRACT = {
    "metric": "dark-surface shadow fire-rate on done-claim Stop turns",
    "owner": "prekzursil",
    "deadline": "2026-08-31",
    "fire_rate": (
        "<5% of done-claim Stop turns surface a live stub marker; "
        "0 confirmed false-positives observed while in shadow"
    ),
}

COMPLETION_RE = re.compile(
    r"\b(?:implemented|wired (?:it |them |this )?(?:up|in)|fully (?:wired|functional|implemented)|"
    r"now (?:works|functional)|plug-and-play|ready to (?:use|go)|feature is (?:complete|done)|"
    r"is (?:now )?(?:complete|implemented|wired|functional)|shipped (?:it|the))\b",
    re.IGNORECASE,
)
STUB_RE = re.compile(
    r"NotImplementedError|raise\s+NotImplemented|"
    r"#\s*(?:TODO|FIXME|STUB|XXX)\b|//\s*(?:TODO|FIXME|STUB|XXX)\b|"
    r"pass\s*#.*\bstub\b|\bplaceholder\b|wire[sd]?\s+this\s+later|deferred\s+to\s+a\s+later",
    re.IGNORECASE,
)
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
)
TEST_HINT = re.compile(
    r"(^|[/\\])(test_|tests?[/\\]|.*\.test\.|.*\.spec\.|conftest)", re.IGNORECASE
)


def _shadow_log(
    gate: str,
    tier: str,
    event: str,
    reason_code: str,
    session_id: str = "",
) -> None:
    """Append a would-have-fired record to the SI-2 shadow sink (fail-open).

    Sink: ``~/.agents/state/harness/shadow/shadow-YYYYMMDD.jsonl`` (rolled at >2MB),
    or ``$HARNESS_SHADOW_DIR`` when set (used by tests to stay hermetic). Record
    shape: ``{ts, gate, tier, event, reason_code, session_hash}``. 1-in-K sampling
    (K=``$HARNESS_SHADOW_SAMPLE``, default 5) applies ONLY to the high-frequency
    PostToolUse/PreToolUse events (Stop is never sampled). This is a SEPARATE
    observability sink — it NEVER writes the event ledger or terminal.jsonl
    (SI-2 / C5 mandate).
    """
    try:
        import datetime
        import hashlib
        import random

        if event in ("PostToolUse", "PreToolUse"):
            try:
                k = int(os.environ.get("HARNESS_SHADOW_SAMPLE", "5") or "5")
            except (TypeError, ValueError):
                k = 5
            if k > 1 and random.randrange(k) != 0:
                return
        override = os.environ.get("HARNESS_SHADOW_DIR")
        base = (
            Path(override)
            if override
            else Path.home() / ".agents" / "state" / "harness" / "shadow"
        )
        base.mkdir(parents=True, exist_ok=True)
        day = datetime.datetime.now().strftime("%Y%m%d")
        sink = base / f"shadow-{day}.jsonl"
        try:
            if sink.exists() and sink.stat().st_size > 2 * 1024 * 1024:
                n = 1
                while (base / f"shadow-{day}.{n}.jsonl").exists():
                    n += 1
                sink.rename(base / f"shadow-{day}.{n}.jsonl")
        except OSError:
            pass
        session_hash = (
            hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]
            if session_id
            else ""
        )
        rec = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "gate": gate,
            "tier": tier,
            "event": event,
            "reason_code": reason_code,
            "session_hash": session_hash,
        }
        with sink.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except Exception:
        pass  # fail-open: shadow logging is best-effort, never crashes the hook


def _final_text(transcript_path: str) -> str:
    p = Path(transcript_path)
    if not p.exists():
        return ""
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
                msg = (
                    ev.get("message")
                    if ev.get("type") == "assistant"
                    else (ev if ev.get("role") == "assistant" else None)
                )
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    c = msg.get("content") or []
                    if isinstance(c, list):
                        parts = [
                            str(b.get("text") or "")
                            for b in c
                            if isinstance(b, dict) and b.get("type") == "text"
                        ]
                    elif isinstance(c, str):
                        parts = [c]
                    else:
                        parts = []
                    if parts:
                        last = " ".join(parts)
    except Exception:
        return ""
    return last


def _edited_files(session_id: str) -> list[str]:
    sid = str(session_id).replace("/", "_").replace("\\", "_")
    f = Path(tempfile.gettempdir()) / "edit-validate" / f"{sid}.edits"
    try:
        seen, out = set(), []
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            p = line.strip()
            if p and p not in seen:
                seen.add(p)
                out.append(p)
        return out
    except Exception:
        return []


def _load_discriminator():
    """``hooks/_shared/use_vs_mention.py``, imported lazily and best-effort.

    Returns ``(Context, classify)`` or ``(None, None)``. Never raises: a missing shared
    module must leave this gate behaving EXACTLY as it did before it was wired, because a
    crashing discriminator would silently disarm a gate -- strictly worse than the false
    positives it replaces.
    """
    try:
        shared = str(THIS.parent / "_shared")
        if shared not in sys.path:
            sys.path.insert(0, shared)
        from use_vs_mention import Context, classify  # noqa: PLC0415

        return Context, classify
    except Exception:  # noqa: BLE001 - no discriminator -> unchanged prior behaviour
        return None, None


# Bound the added cost. dark-surface is a Stop hook and the Stop battery already runs
# hot (measured 2026-08-07: 63.7s against a 35s host wall), so the wiring must not be
# able to grow without limit. The AST string-literal parse is the only non-trivial cost
# and it is paid at most once per FILE (`_string_literal_spans` is memoised upstream);
# these caps bound the per-file match count and the total scan.
_MAX_MARKERS_PER_FILE = 200
_MAX_HITS = 6  # == the number the message shows; scanning past it changes nothing


def _real_occurrence(discrim, text, span, *, kind, file_path="", source="file") -> bool:
    """True when the match at `span` is a real occurrence (fail-open on any failure)."""
    Context, classify = discrim
    if Context is None or classify is None:
        return True  # no discriminator -> exactly the pre-wiring behaviour
    try:
        return classify(
            text, span, Context(file_path=file_path, source=source), kind=kind
        ).is_real
    except Exception:  # noqa: BLE001 - never silence a gate on an internal error
        return True


def main() -> int:
    try:
        if (THIS / ".disabled").exists() or os.environ.get(
            "DARK_SURFACE", ""
        ).lower() in ("off", "0", "false"):
            return 0
        data = json.loads(sys.stdin.read() or "{}")
        if data.get("stop_hook_active"):
            return 0  # anti-loop
        text = _final_text(str(data.get("transcript_path") or ""))
        if not text:
            return 0
        discrim = _load_discriminator()
        # kind="claim", NOT "marker" -- see the module docstring. A claim ASSERTED in
        # prose is real; it is a mention only when the message is quoting the phrase
        # (fenced block / inline code span), e.g. a report that pastes this hook's own
        # COMPLETION_RE, which contains the literal word "implemented".
        claimed = False
        for i, cm in enumerate(COMPLETION_RE.finditer(text)):
            if i >= _MAX_MARKERS_PER_FILE:
                claimed = True  # too many to judge -> fail-open, treat as a claim
                break
            if _real_occurrence(
                discrim, text, cm.span(), kind="claim", source="assistant_message"
            ):
                claimed = True
                break
        if not claimed:
            return 0  # no completion claim -> silent
        hits = []
        for fp in _edited_files(str(data.get("session_id") or "unknown")):
            if len(hits) >= _MAX_HITS:
                break  # the message only ever shows _MAX_HITS; scanning on is dead work
            if not fp.endswith(SRC_EXT) or TEST_HINT.search(fp):
                continue
            try:
                if not os.path.exists(fp):
                    continue
                body = Path(fp).read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            # kind="stub": the evidence bar is a marker in CODE. A marker spelled inside
            # a string literal is corpus data or a code template, not pending work --
            # all six recorded fires were exactly that.
            for i, m in enumerate(STUB_RE.finditer(body)):
                if i >= _MAX_MARKERS_PER_FILE:
                    break
                if _real_occurrence(discrim, body, m.span(), kind="stub", file_path=fp):
                    hits.append((os.path.basename(fp), m.group(0).strip()[:30]))
                    break
        if hits:
            shown = "; ".join(f"{n} ({mk})" for n, mk in hits[:6])

            # A6 — SHADOW gate (default). Observe only: record the would-have-fired
            # verdict to the SI-2 sink and surface a clearly-labelled [SHADOW] note.
            # (This gate never blocked; shadow only relabels + logs.) Set
            # DARK_SURFACE_MODE=live for the original plain nudge with no sink write.
            if DARK_SURFACE_MODE == "shadow":
                _shadow_log(
                    gate="dark-surface",
                    tier="heuristic",
                    event=str(data.get("hook_event_name") or "Stop"),
                    reason_code="dark_surface:stub_marker",
                    session_id=str(data.get("session_id") or ""),
                )
                msg = (
                    "**[SHADOW] dark-surface / stub check (observe-only)** Your message claims something "
                    f"is implemented/done, but a source file you edited this session still contains a "
                    f"STUB/placeholder marker: {shown}. Logged to the shadow sink; not enforced. Verify "
                    "the feature is actually WIRED + functional (not a NotImplementedError / TODO / "
                    "placeholder) and that a production (non-test) path actually calls it — green tests "
                    "can pass over a dark surface. (SHADOW mode — set DARK_SURFACE_MODE=live to enforce.)"
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
                return 0

            msg = (
                "**[dark-surface / stub check]** Your message claims something is implemented/done, but a "
                f"source file you edited this session still contains a STUB/placeholder marker: {shown}. "
                "Verify the feature is actually WIRED + functional (not a NotImplementedError / TODO / "
                "placeholder) and that a production (non-test) path actually calls it — green tests can pass "
                "over a dark surface. If it is genuinely a deferred stub, say so explicitly rather than 'done'."
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
        pass  # fail-open: never crash a session
    return 0


if __name__ == "__main__":
    sys.exit(main())
