#!/usr/bin/env python3
"""Tests for background-digest/reader.py. Runs standalone (`python test_background_digest.py`)
AND under pytest.

The historical `main()` body below is a standalone assertion suite; `test_legacy_suite()`
at the bottom re-exports it to pytest, because the only CI step that reaches this file is
`python -m pytest hooks/ -q` (quality.yml:702) and a file with no `test_*` callable is
collected with ZERO tests. Regression tests for ranked surfacing live in the `test_*`
functions below them.

Isolates the digest + archive into a temp dir via env (set BEFORE import) so the real
~/.claude/BACKGROUND-DIGEST.md is never touched.
"""

import importlib.util
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="bgdigest-test-"))
os.environ["BG_DIGEST_FILE"] = str(_TMP / "BACKGROUND-DIGEST.md")
os.environ["BG_DIGEST_ARCHIVE"] = str(_TMP / "BACKGROUND-DIGEST.archive.log")
os.environ["BG_DIGEST_MAX"] = "3"  # small cap to exercise overflow
os.environ["BG_DIGEST_ARCHIVE_MAX"] = "100"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reader as R  # noqa: E402

# belt-and-suspenders: rebind module constants even if env timing slipped
R.DIGEST_FILE = Path(os.environ["BG_DIGEST_FILE"])
R.ARCHIVE_FILE = Path(os.environ["BG_DIGEST_ARCHIVE"])
R.MAX_SURFACE = 3
R.ARCHIVE_MAX = 100

_FAILS = []


def ok(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        _FAILS.append(name)


def write_digest(text):
    R.DIGEST_FILE.write_text(text, encoding="utf-8")


def read_digest():
    return R.DIGEST_FILE.read_text(encoding="utf-8") if R.DIGEST_FILE.exists() else ""


def reset():
    for p in (R.DIGEST_FILE, R.ARCHIVE_FILE):
        try:
            p.unlink()
        except FileNotFoundError:
            pass


HEADER = "<!-- BACKGROUND-DIGEST: producers append [date] lines; reader surfaces+truncates. -->"
E1 = "[2026-06-29 09:00:00] [resource-guard] RAM 3.0GB free (<4) | PROPOSE: mcp_doctor reap"
E2 = "[2026-06-29 10:00:00] [world-watch] BC 15.4.1->15.5: offsets need re-derivation | PROPOSE: review"
E3 = "[2026-06-29 11:00:00] [world-watch] HexStrike HEAD changed | PROPOSE: check patches"
E4 = "[2026-06-29 12:00:00] [resource-guard] C: 94% used (>=90) | PROPOSE: cleanup-c-drive.ps1"


def run_main(payload="{}"):
    """Invoke reader.main([]) the dispatcher way (stdin routed, stdout captured)."""
    buf = io.StringIO()
    old = sys.stdin
    sys.stdin = io.StringIO(payload)
    try:
        with redirect_stdout(buf):
            R.main([])
    finally:
        sys.stdin = old
    return buf.getvalue()


def surfaced_ctx(out):
    for line in out.splitlines():
        try:
            o = json.loads(line)
        except Exception:
            continue
        ctx = (o.get("hookSpecificOutput") or {}).get("additionalContext")
        if ctx:
            return ctx
    return None


def main():
    # ---- 1. missing file -> silent, no crash --------------------------------
    reset()
    out = run_main()
    ok("missing digest -> emits nothing", surfaced_ctx(out) is None)

    # ---- 2. header-only / no entries -> silent ------------------------------
    reset()
    write_digest(HEADER + "\n\n")
    msg, surf = R.build_message(R._read_lines(R.DIGEST_FILE))
    ok("header-only -> no message", msg is None and surf == [])

    # ---- 3. surfaces entries + preserves header on consume ------------------
    reset()
    write_digest("\n".join([HEADER, E1, E2]) + "\n")
    out = run_main()
    ctx = surfaced_ctx(out)
    ok(
        "surfaces both entries",
        ctx is not None and "RAM 3.0GB" in ctx and "BC 15.4.1" in ctx,
    )
    ok(
        "surfaced text is wrapped with the header banner",
        ctx is not None and "While you were away" in ctx,
    )
    after = read_digest()
    ok("consumed entries truncated from live file", E1 not in after and E2 not in after)
    ok("non-entry header PRESERVED after truncate", HEADER in after)
    arch = R.ARCHIVE_FILE.read_text(encoding="utf-8") if R.ARCHIVE_FILE.exists() else ""
    ok("consumed entries archived (loss-proof)", E1 in arch and E2 in arch)

    # ---- 4. surface-once: second start surfaces nothing ---------------------
    out2 = run_main()
    ok("already-consumed -> second SessionStart is silent", surfaced_ctx(out2) is None)

    # ---- 5. FIFO cap + overflow note; overflow survives to next run ---------
    reset()
    write_digest("\n".join([E1, E2, E3, E4]) + "\n")  # 4 entries, cap=3
    out = run_main()
    ctx = surfaced_ctx(out)
    ok(
        "cap=3 surfaces the 3 oldest (FIFO)",
        ctx is not None and E1 in ctx and E2 in ctx and E3 in ctx,
    )
    ok("4th (newest) entry NOT surfaced this run", ctx is not None and E4 not in ctx)
    ok("overflow note shown", ctx is not None and "+1 more pending" in ctx)
    after = read_digest()
    ok("overflow entry retained in live file", E4 in after)
    ok("surfaced entries removed from live file", E1 not in after and E3 not in after)
    out = run_main()
    ok(
        "overflow surfaces on the next run",
        (surfaced_ctx(out) or "").find("C: 94%") >= 0,
    )

    # ---- 6. concurrency: an append between read and truncate is preserved ---
    reset()
    write_digest("\n".join([E1, E2]) + "\n")
    lines = R._read_lines(R.DIGEST_FILE)
    msg, surf = R.build_message(lines)
    ok("build_message picked the entries", msg is not None and len(surf) == 2)
    # simulate a producer appending E3 AFTER the reader's initial read
    with R.DIGEST_FILE.open("a", encoding="utf-8") as fh:
        fh.write(E3 + "\n")
    R._truncate_consumed(surf)  # truncates from a FRESH read -> must keep E3
    after = read_digest()
    ok("concurrent append survives truncation", E3 in after)
    ok("originally-surfaced entries still removed", E1 not in after and E2 not in after)

    # ---- 7. fail-open on garbage / non-text content -------------------------
    reset()
    R.DIGEST_FILE.write_bytes(b"\xff\xfe\x00garbage\x00\x80\x81 not-an-entry\n")
    try:
        out = run_main()
        crashed = False
    except Exception:
        crashed = True
    ok("binary garbage -> no crash (fail-open)", not crashed)
    ok("garbage with no entry lines -> nothing surfaced", surfaced_ctx(out) is None)

    # ---- 8. opt-out via env --------------------------------------------------
    reset()
    write_digest(E1 + "\n")
    os.environ["BG_DIGEST"] = "off"
    try:
        out = run_main()
        ok("BG_DIGEST=off -> silent", surfaced_ctx(out) is None)
        ok("BG_DIGEST=off -> live file untouched (not consumed)", E1 in read_digest())
    finally:
        os.environ.pop("BG_DIGEST", None)

    # ---- 9. archive rotation bounded ----------------------------------------
    reset()
    R.ARCHIVE_MAX = 5
    big = "\n".join(
        f"[2026-06-29 0{i}:00:00] [t] line{i} | PROPOSE: x" for i in range(9)
    )
    write_digest(big + "\n")
    R.MAX_SURFACE = 50
    run_main()
    arch_lines = [
        ln
        for ln in R.ARCHIVE_FILE.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    ok("archive rotated to ARCHIVE_MAX", len(arch_lines) <= 5)
    R.MAX_SURFACE = 3
    R.ARCHIVE_MAX = 100

    # ---- 10. SUBAGENT guard: a subagent SessionStart must NOT surface or consume -----
    reset()
    write_digest(E1 + "\n")
    sub = json.dumps(
        {
            "source": "startup",
            "transcript_path": "C:/Users/x/.claude/projects/proj/sess/subagents/agent-abc.jsonl",
        }
    )
    out = run_main(sub)
    ok("subagent SessionStart surfaces nothing", surfaced_ctx(out) is None)
    ok(
        "subagent SessionStart does NOT consume (kept for main session)",
        E1 in read_digest(),
    )
    main_pl = json.dumps(
        {
            "source": "startup",
            "transcript_path": "C:/Users/x/.claude/projects/proj/sess.jsonl",
        }
    )
    out = run_main(main_pl)
    ok("main-session payload DOES surface", surfaced_ctx(out) is not None)
    ok("main-session payload DOES consume", E1 not in read_digest())

    # ---- 11. archive-failure gate: surfaced but NOT truncated (loss-proof) ------------
    reset()
    write_digest(E2 + "\n")
    _orig_archive = R._archive
    R._archive = lambda consumed: False
    try:
        out = run_main()
        ok("archive-fail still surfaces", surfaced_ctx(out) is not None)
        ok(
            "archive-fail does NOT truncate (re-surfaces next session, not lost)",
            E2 in read_digest(),
        )
    finally:
        R._archive = _orig_archive

    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


# ---------------------------------------------------------------------------------
# pytest-collectable regression tests (ranked surfacing / attention budget).
# `python -m pytest hooks/ -q` (quality.yml:702) is the only CI step that reaches this
# file, and it collects nothing unless a callable is named test_*.
# ---------------------------------------------------------------------------------

URGENT = (
    "[2026-07-27 00:01:00] [resource-guard] NEEDS_YOU: disk full; builds blocked "
    "| PROPOSE: free space"
)
ROUTINE = [f"[2026-07-26 {i:02d}:00:00] [idle] routine-{i:02d}" for i in range(12)]


def _with_cap(cap, lines):
    """Call the PURE builder at a fixed cap, restoring the module constant after."""
    prev = R.MAX_SURFACE
    R.MAX_SURFACE = cap
    try:
        return R.build_message(lines)
    finally:
        R.MAX_SURFACE = prev


def test_urgent_entry_is_not_buried_by_older_routine_chatter():
    """D-j04: 12 older routine notices + 1 later NEEDS_YOU, 12 slots.

    Pre-fix (`entries[:MAX_SURFACE]`) the urgent record fell into overflow. Ranked
    selection must surface it, and as the FIRST card.
    """
    msg, surfaced = _with_cap(12, [*ROUTINE, URGENT])
    assert URGENT in surfaced, "urgent record was deferred to overflow"
    cards = [ln for ln in msg.splitlines() if ln.startswith("[")]
    assert cards[0] == URGENT, f"urgent record not ranked first; got {cards[0]!r}"
    # FIFO within a band still holds: the routine cards keep queue order.
    assert cards[1:] == ROUTINE[:11]


def test_urgent_survives_the_three_card_attention_budget():
    """D-j01 + D-j04 together: at the default 3-slot budget the urgent record is kept
    and the displaced routine chatter is reported as overflow, never dropped."""
    msg, surfaced = _with_cap(3, [*ROUTINE, URGENT])
    assert URGENT in surfaced
    assert len(surfaced) == 3
    assert "...(+10 more pending" in msg


def test_identical_repeated_state_coalesces_to_one_card_without_loss():
    """D-j04 (coalesce): 100 byte-identical idle notices must cost ONE card, and every
    collapsed line must still be consumed so it reaches the archive."""
    chatter = [
        f"[2026-07-26 {i % 24:02d}:00:00] [idle] agent-7 idle" for i in range(100)
    ]
    msg, surfaced = _with_cap(3, [*chatter, URGENT])
    cards = [ln for ln in msg.splitlines() if ln.startswith("[")]
    assert len(cards) == 2, f"expected urgent + 1 coalesced card, got {len(cards)}"
    assert cards[0] == URGENT
    assert "(x100 observations)" in cards[1]
    assert len(surfaced) == 101, "coalesced repeats must still be consumed/archived"
    assert "more pending" not in msg


def test_ranking_is_deterministic():
    """Same input -> same order, twice (no clock, no set iteration order)."""
    a, _ = _with_cap(5, [*ROUTINE, URGENT])
    b, _ = _with_cap(5, [*ROUTINE, URGENT])
    assert a == b


def test_default_attention_budget_is_three():
    """D-j01: the UNSET-env default. This module pins BG_DIGEST_MAX=3 at import, so the
    default is measured by executing a FRESH copy of reader.py with the variable popped.
    BG_DIGEST_FILE/ARCHIVE stay pointed at the temp dir, so ~/.claude is still untouched.
    """
    saved = os.environ.pop("BG_DIGEST_MAX", None)
    try:
        spec = importlib.util.spec_from_file_location(
            "reader_default_probe", R.__file__
        )
        fresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fresh)
    finally:
        if saved is not None:
            os.environ["BG_DIGEST_MAX"] = saved
    assert fresh.MAX_SURFACE == 3, (
        f"default BG_DIGEST_MAX is {fresh.MAX_SURFACE}, exceeding the 3-delta "
        "SessionStart attention budget"
    )


def test_legacy_suite():
    """Run the standalone assertion suite above under pytest (it was never collected)."""
    assert main() == 0, f"standalone suite failures: {_FAILS}"


if __name__ == "__main__":
    sys.exit(main())
