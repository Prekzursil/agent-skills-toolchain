#!/usr/bin/env python3
"""Tests for background-digest/reader.py. Runs WITHOUT pytest: `python test_background_digest.py`.

Isolates the digest + archive into a temp dir via env (set BEFORE import) so the real
~/.claude/BACKGROUND-DIGEST.md is never touched.
"""
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
os.environ["BG_DIGEST_MAX"] = "3"            # small cap to exercise overflow
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
    ok("surfaces both entries", ctx is not None and "RAM 3.0GB" in ctx and "BC 15.4.1" in ctx)
    ok("surfaced text is wrapped with the header banner",
       ctx is not None and "While you were away" in ctx)
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
    ok("cap=3 surfaces the 3 oldest (FIFO)",
       ctx is not None and E1 in ctx and E2 in ctx and E3 in ctx)
    ok("4th (newest) entry NOT surfaced this run", ctx is not None and E4 not in ctx)
    ok("overflow note shown", ctx is not None and "+1 more pending" in ctx)
    after = read_digest()
    ok("overflow entry retained in live file", E4 in after)
    ok("surfaced entries removed from live file", E1 not in after and E3 not in after)
    out = run_main()
    ok("overflow surfaces on the next run", (surfaced_ctx(out) or "").find("C: 94%") >= 0)

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
    big = "\n".join(f"[2026-06-29 0{i}:00:00] [t] line{i} | PROPOSE: x" for i in range(9))
    write_digest(big + "\n")
    R.MAX_SURFACE = 50
    run_main()
    arch_lines = [l for l in R.ARCHIVE_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    ok("archive rotated to ARCHIVE_MAX", len(arch_lines) <= 5)
    R.MAX_SURFACE = 3
    R.ARCHIVE_MAX = 100

    # ---- 10. SUBAGENT guard: a subagent SessionStart must NOT surface or consume -----
    reset()
    write_digest(E1 + "\n")
    sub = json.dumps({"source": "startup",
                      "transcript_path": "C:/Users/x/.claude/projects/proj/sess/subagents/agent-abc.jsonl"})
    out = run_main(sub)
    ok("subagent SessionStart surfaces nothing", surfaced_ctx(out) is None)
    ok("subagent SessionStart does NOT consume (kept for main session)", E1 in read_digest())
    main_pl = json.dumps({"source": "startup",
                          "transcript_path": "C:/Users/x/.claude/projects/proj/sess.jsonl"})
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
        ok("archive-fail does NOT truncate (re-surfaces next session, not lost)", E2 in read_digest())
    finally:
        R._archive = _orig_archive

    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
