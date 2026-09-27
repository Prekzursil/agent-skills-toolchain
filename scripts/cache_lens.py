#!/usr/bin/env python3
"""cache_lens.py - prompt-cache hit-rate + cold-prefix-rewrite lens.

Reads the prefix-cache usage fields that nothing on this estate otherwise reads:
`cache_read_input_tokens`, `cache_creation_input_tokens`, `input_tokens`,
`output_tokens` from assistant messages in ~/.claude/projects/**/*.jsonl.

WHY DEDUPE (load-bearing): a single assistant message is logged on MULTIPLE
transcript lines - one per content block (text / tool_use / ...). Measured
2026-09-25 across the three largest transcripts: mean 2.05-2.71 lines per
message.id, tail up to 25-30x, and the IDENTICAL usage block is copied onto
every one of those lines (distinct usage tuples per id = 1). So a naive sum over
assistant lines inflates every token total by the per-file mean multiplicity.
The estate's own ground-truth artifact shows this directly ("547,163 x4" = one
message counted four times). We dedupe by message.id (safe: usage is identical
across the duplicate lines) and PROVE the dedupe with a before/after count and a
deterministic self-test fixture (--selftest).

Definitions:
  hit rate            = sum(cache_read) / sum(cache_read + cache_creation + input)
  cold prefix rewrite = a (deduped) assistant message with
                        cache_creation > COLD_THRESHOLD tokens AND cache_read == 0
                        (a full prefix re-encode paid from cold, ~once per cold start)
  flagged session     = one whose summed cold-rewrite creation cost exceeds
                        --session-flag-threshold

All output is aggregates, never a transcript dump. Ends with a §4 terminal marker.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import tempfile

DEFAULT_ROOT = os.path.expandvars(r"%USERPROFILE%\.claude\projects")
if "%USERPROFILE%" in DEFAULT_ROOT or not os.path.isdir(DEFAULT_ROOT):
    DEFAULT_ROOT = os.path.join(os.path.expanduser("~"), ".claude", "projects")


def _usage_tuple(u: dict) -> tuple[int, int, int, int]:
    return (
        int(u.get("input_tokens", 0) or 0),
        int(u.get("cache_read_input_tokens", 0) or 0),
        int(u.get("cache_creation_input_tokens", 0) or 0),
        int(u.get("output_tokens", 0) or 0),
    )


def scan_file(path: str):
    """Return (deduped_records, raw_line_count).

    deduped_records: list of dicts, ONE per unique assistant message.id, each
    carrying its usage tuple. raw_line_count: assistant lines that carried usage
    (the pre-dedupe count) - reported so the dedupe is auditable.
    """
    seen: dict = {}
    raw_usage_lines = 0
    fallback_idx = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("type") != "assistant":
                continue
            msg = o.get("message") or {}
            u = msg.get("usage") or {}
            if not u:
                continue
            raw_usage_lines += 1
            mid = msg.get("id")
            if not mid:
                # Fallback key: (timestamp, requestId, running index) so a
                # message with no id is never silently merged with another.
                mid = ("noid", o.get("timestamp"), o.get("requestId"), fallback_idx)
                fallback_idx += 1
            if mid in seen:
                # Same message, another content-block line. Usage is identical
                # (verified); keep the first, do not double count.
                continue
            it, cr, cc, ot = _usage_tuple(u)
            seen[mid] = {
                "id": mid if isinstance(mid, str) else "noid",
                "ts": (o.get("timestamp") or "")[:19],
                "in": it,
                "cr": cr,
                "cc": cc,
                "out": ot,
            }
    return list(seen.values()), raw_usage_lines


def summarize(records, cold_threshold: int):
    tot_in = sum(r["in"] for r in records)
    tot_cr = sum(r["cr"] for r in records)
    tot_cc = sum(r["cc"] for r in records)
    tot_out = sum(r["out"] for r in records)
    billed = tot_in + tot_cr + tot_cc
    hit = (tot_cr / billed * 100.0) if billed else 0.0
    cold = [r for r in records if r["cc"] > cold_threshold and r["cr"] == 0]
    cold_cost = sum(r["cc"] for r in cold)
    return {
        "msgs": len(records),
        "in": tot_in, "cr": tot_cr, "cc": tot_cc, "out": tot_out,
        "hit_rate": hit,
        "cold_rewrites": len(cold),
        "cold_cost": cold_cost,
    }


def run_selftest() -> int:
    """Deterministic both-states proof of the dedupe.

    Build a synthetic transcript with ONE message.id repeated 3x (identical
    usage) plus one distinct single-line message. Assert:
      raw sum counts the repeated usage 3x (BROKEN behaviour), and
      deduped sum counts it once (CORRECT behaviour).
    A dedupe that silently did nothing would make both equal and FAIL here.
    """
    rep = {"input_tokens": 100, "cache_read_input_tokens": 10,
           "cache_creation_input_tokens": 30000, "output_tokens": 5}
    other = {"input_tokens": 7, "cache_read_input_tokens": 9,
             "cache_creation_input_tokens": 1, "output_tokens": 3}
    lines = []
    for _ in range(3):  # one message, three content-block lines, same usage
        lines.append({"type": "assistant", "timestamp": "2026-09-25T00:00:00Z",
                      "message": {"id": "msg_REPEATED", "usage": rep}})
    lines.append({"type": "assistant", "timestamp": "2026-09-25T00:00:01Z",
                  "message": {"id": "msg_OTHER", "usage": other}})
    lines.append({"type": "user", "message": {"role": "user"}})  # ignored

    fd, p = tempfile.mkstemp(suffix=".jsonl", prefix="cache_lens_selftest_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for o in lines:
                f.write(json.dumps(o) + "\n")
        records, raw_lines = scan_file(p)
    finally:
        os.unlink(p)

    # BROKEN state: naive sum over every usage-bearing line.
    raw_cc = 3 * rep["cache_creation_input_tokens"] + other["cache_creation_input_tokens"]
    # CORRECT state: deduped.
    dd = summarize(records, cold_threshold=20000)

    ok = True
    checks = []

    c1 = (raw_lines == 4)
    checks.append(f"  raw usage-bearing lines      : {raw_lines}  (expect 4)  {'OK' if c1 else 'FAIL'}")
    ok &= c1

    c2 = (dd["msgs"] == 2)
    checks.append(f"  deduped unique messages      : {dd['msgs']}  (expect 2)  {'OK' if c2 else 'FAIL'}")
    ok &= c2

    c3 = (dd["cc"] == rep["cache_creation_input_tokens"] + other["cache_creation_input_tokens"])
    checks.append(f"  deduped cache_creation total : {dd['cc']:,}  (expect {rep['cache_creation_input_tokens']+other['cache_creation_input_tokens']:,})  {'OK' if c3 else 'FAIL'}")
    ok &= c3

    # The BROKEN behaviour must differ from the CORRECT one, or the dedupe is inert.
    c4 = (raw_cc != dd["cc"]) and (raw_cc == 90001)
    checks.append(f"  raw(undeduped) cache_creation: {raw_cc:,}  differs from deduped, inflated {raw_cc/dd['cc']:.2f}x  {'OK' if c4 else 'FAIL'}")
    ok &= c4

    c5 = (dd["cold_rewrites"] == 0)  # rep has cr=10 (>0), so NOT a cold rewrite
    checks.append(f"  cold rewrites (cr>0 excluded): {dd['cold_rewrites']}  (expect 0)  {'OK' if c5 else 'FAIL'}")
    ok &= c5

    # Now flip ONE field to prove the cold-rewrite detector FIRES on a broken input.
    rep_cold = dict(rep)
    rep_cold["cache_read_input_tokens"] = 0
    fd, p = tempfile.mkstemp(suffix=".jsonl", prefix="cache_lens_selftest2_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "assistant", "timestamp": "2026-09-25T00:00:02Z",
                                "message": {"id": "msg_COLD", "usage": rep_cold}}) + "\n")
        rec2, _ = scan_file(p)
    finally:
        os.unlink(p)
    dd2 = summarize(rec2, cold_threshold=20000)
    c6 = (dd2["cold_rewrites"] == 1)
    checks.append(f"  cold detector FIRES on cr==0 : {dd2['cold_rewrites']}  (expect 1)  {'OK' if c6 else 'FAIL'}")
    ok &= c6

    print("SELF-TEST (deterministic dedupe + cold-detector both-states proof):")
    print("\n".join(checks))
    if ok:
        print("\nSUCCESS:cache_lens_selftest")
        return 0
    print("\nFAILED:cache_lens_selftest one or more assertions failed")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="prompt-cache hit-rate + cold-prefix-rewrite lens")
    ap.add_argument("--root", default=DEFAULT_ROOT,
                    help="projects dir to scan (default: ~/.claude/projects)")
    ap.add_argument("--cold-threshold", type=int, default=20000,
                    help="cache_creation floor (with read==0) for a cold prefix rewrite")
    ap.add_argument("--session-flag-threshold", type=int, default=500000,
                    help="flag a session whose summed cold-rewrite cost exceeds this")
    ap.add_argument("--top", type=int, default=15, help="how many worst sessions to list")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--selftest", action="store_true", help="run the deterministic dedupe proof and exit")
    args = ap.parse_args(argv)

    if args.selftest:
        return run_selftest()

    if not os.path.isdir(args.root):
        print(f"FAILED:cache_lens root not found: {args.root}")
        return 1

    files = glob.glob(os.path.join(args.root, "**", "*.jsonl"), recursive=True)
    if not files:
        print(f"FAILED:cache_lens no .jsonl under {args.root}")
        return 1

    sessions = []
    g_raw_lines = 0
    g_records = []
    for f in files:
        try:
            recs, raw_lines = scan_file(f)
        except Exception as e:  # never let one bad file abort the sweep
            sessions.append({"file": os.path.basename(f), "error": str(e)})
            continue
        if not recs:
            continue
        g_raw_lines += raw_lines
        g_records.extend(recs)
        s = summarize(recs, args.cold_threshold)
        s["file"] = os.path.basename(f)
        s["raw_usage_lines"] = raw_lines
        sessions.append(s)

    g = summarize(g_records, args.cold_threshold)
    dedupe_factor = (g_raw_lines / g["msgs"]) if g["msgs"] else 0.0
    flagged = sorted(
        [s for s in sessions if s.get("cold_cost", 0) > args.session_flag_threshold],
        key=lambda x: -x["cold_cost"],
    )

    if args.json:
        print(json.dumps({
            "root": args.root, "files": len(files),
            "raw_usage_lines": g_raw_lines, "deduped_messages": g["msgs"],
            "dedupe_factor": round(dedupe_factor, 3),
            "totals": {k: g[k] for k in ("in", "cr", "cc", "out")},
            "hit_rate_pct": round(g["hit_rate"], 2),
            "cold_rewrites": g["cold_rewrites"], "cold_cost": g["cold_cost"],
            "flagged_sessions": [
                {"file": s["file"], "cold_cost": s["cold_cost"],
                 "cold_rewrites": s["cold_rewrites"], "hit_rate_pct": round(s["hit_rate"], 2)}
                for s in flagged],
        }, indent=2))
        print("\nSUCCESS:cache_lens")
        return 0

    print(f"root: {args.root}")
    print(f"transcript files scanned : {len(files):,}")
    print("\n-- DEDUPE PROOF (before/after) --")
    print(f"  raw assistant usage lines : {g_raw_lines:,}   <- naive sum would use this")
    print(f"  deduped unique messages   : {g['msgs']:,}   <- correct basis")
    if g["msgs"]:
        print(f"  inflation if NOT deduped  : {dedupe_factor:.2f}x  (every token total would be this much too high)")
    print("\n-- TOTALS (deduped) --")
    print(f"  cache_read_input_tokens   : {g['cr']:,}")
    print(f"  cache_creation_input_tokens: {g['cc']:,}")
    print(f"  uncached input_tokens     : {g['in']:,}")
    print(f"  output_tokens             : {g['out']:,}")
    print(f"  cache HIT rate            : {g['hit_rate']:.2f}%  (read / all input)")
    print("\n-- COLD PREFIX REWRITES (creation > "
          f"{args.cold_threshold:,} AND read == 0) --")
    print(f"  count (deduped)           : {g['cold_rewrites']:,}")
    print(f"  total cold creation cost  : {g['cold_cost']:,} tok")
    print(f"\n-- SESSIONS flagged (cold cost > {args.session_flag_threshold:,}) : {len(flagged)} --")
    for s in flagged[: args.top]:
        print(f"    {s['file']:40}  cold={s['cold_cost']:>12,}  "
              f"rewrites={s['cold_rewrites']:>4}  hit={s['hit_rate']:5.1f}%")
    print("\nSUCCESS:cache_lens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
