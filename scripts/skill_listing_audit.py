#!/usr/bin/env python3
"""skill_listing_audit.py - skill-listing truncation visibility.

Every session injects a listing of available skills - one `name: description` line
per SKILL.md - and that listing is capped at `skillListingBudgetFraction` of the
context window (default 0.04). When the frontmatter of all discovered skills exceeds
the cap, the listing is TRUNCATED: skills past the budget are silently dropped from
what the model can see. This tool makes the go/no-go on lowering the fraction obvious.

It reports, across local + plugin SKILL.md roots:
  - total SKILL.md count
  - total name+description bytes (the listing payload; description is ~95% of it)
  - the implied token cost (bytes / chars-per-token, default 4 - the estate's own
    heuristic: 136,778 B -> 34,194 tok is exactly /4)
  - for each --window: whether the 0.04 cap BINDS (listing > cap => truncation) or is
    NON-BINDING, computed for LOCAL-ONLY and for LOCAL+PLUGIN so the flip is visible.

Local roots default to ~/.claude/skills (what the session loads); ~/.agents/skills is
its authored mirror and is reported informationally, NOT added to the listing total.
Plugin root defaults to ~/.claude/plugins.

Both-states proof: --selftest builds synthetic skill trees and asserts a tiny listing
under a huge window is NON-BINDING while a huge listing under a tiny window BINDS, and
that the frontmatter parser extracts name+description on a good file and contributes
zero (not a crash) on a file with no frontmatter.
"""
from __future__ import annotations

import argparse
import os
import re
import tempfile

HOME = os.path.expanduser("~")
DEF_LOCAL = os.path.join(HOME, ".claude", "skills")
DEF_PLUGIN = os.path.join(HOME, ".claude", "plugins")
DEF_MIRROR = os.path.join(HOME, ".agents", "skills")

_KEY = re.compile(r"^([A-Za-z_][\w-]*):\s?(.*)$")


def parse_frontmatter(text: str) -> tuple[str, str]:
    """Extract (name, description) from a SKILL.md's leading YAML frontmatter.

    Handles inline scalars, quoted values, and folded/literal block scalars
    (`>`/`|`) with indented continuation lines. Returns ("","") when there is no
    frontmatter - counted, never crashed.
    """
    if not text.startswith("---"):
        return "", ""
    lines = text.splitlines()
    # frontmatter is between the first '---' and the next line that is exactly '---'
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return "", ""
    body = lines[1:end]

    fields: dict[str, str] = {}
    i = 0
    while i < len(body):
        line = body[i]
        m = _KEY.match(line)
        if not m:
            i += 1
            continue
        key, val = m.group(1).lower(), m.group(2).strip()
        if val in (">", "|", ">-", "|-", ">+", "|+", ""):
            # block scalar / empty inline -> gather indented continuation lines
            parts = []
            j = i + 1
            while j < len(body):
                nxt = body[j]
                if nxt.strip() == "":
                    parts.append("")
                    j += 1
                    continue
                if nxt[:1] in (" ", "\t"):
                    parts.append(nxt.strip())
                    j += 1
                    continue
                break  # next top-level key
            val = (val if val not in (">", "|", ">-", "|-", ">+", "|+") else "").strip()
            joined = " ".join(p for p in parts if p != "")
            val = (val + " " + joined).strip() if val else joined
            i = j
        else:
            val = val.strip().strip('"').strip("'")
            i += 1
        fields[key] = val
    return fields.get("name", ""), fields.get("description", "")


def scan_root(root: str):
    """Return (count, name_desc_bytes) over all SKILL.md under root.

    Uses os.walk (followlinks=False) rather than glob('**'): glob silently skips
    symlinked/junction directories, and there are junctions under ~/.claude/plugins,
    so glob undercounts (measured 2026-09-25: glob 2,057 vs os.walk/find 2,167).
    followlinks=False still avoids descending INTO junction targets (node_modules
    loops), so this is the complete on-disk SKILL.md set without double-counting.
    """
    if not os.path.isdir(root):
        return 0, 0
    count = 0
    total_bytes = 0
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for fn in filenames:
            if fn.lower() != "skill.md":
                continue
            count += 1
            try:
                with open(os.path.join(dirpath, fn), encoding="utf-8") as f:
                    text = f.read()
            except Exception:
                continue
            name, desc = parse_frontmatter(text)
            total_bytes += len((name + desc).encode("utf-8"))
    return count, total_bytes


def toks(nbytes: int, cpt: float) -> int:
    return int(nbytes / cpt) if cpt else 0


def binding(listing_tokens: int, window: int, fraction: float):
    cap = int(window * fraction)
    return cap, ("BINDS" if listing_tokens > cap else "NON-BINDING"), (listing_tokens - cap)


def run_selftest() -> int:
    tmp = tempfile.mkdtemp(prefix="skill_audit_selftest_")
    # good skill with real frontmatter
    good = os.path.join(tmp, "good")
    os.makedirs(good)
    with open(os.path.join(good, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("---\nname: alpha\ndescription: " + ("x" * 400) + "\n---\nbody\n")
    # block-scalar description
    blk = os.path.join(tmp, "blk")
    os.makedirs(blk)
    with open(os.path.join(blk, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("---\nname: beta\ndescription: >\n  " + ("y" * 100) + "\n  " + ("z" * 100) + "\n---\n")
    # NO frontmatter -> must contribute 0, not crash
    bad = os.path.join(tmp, "bad")
    os.makedirs(bad)
    with open(os.path.join(bad, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("no frontmatter here\njust text\n")

    cnt, nbytes = scan_root(tmp)
    n_alpha, d_alpha = parse_frontmatter("---\nname: alpha\ndescription: " + ("x" * 400) + "\n---\n")
    n_none, d_none = parse_frontmatter("no frontmatter\n")

    checks = []
    ok = True

    c1 = (cnt == 3)
    checks.append(f"  SKILL.md discovered          : {cnt}  (expect 3)  {'OK' if c1 else 'FAIL'}")
    ok &= c1

    # good(5+400) + blk(4 + 201[100+100+1 space]) + bad(0)
    expect_bytes = len("alpha") + 400 + len("beta") + 201
    c2 = (nbytes == expect_bytes)
    checks.append(f"  name+desc bytes              : {nbytes}  (expect {expect_bytes})  {'OK' if c2 else 'FAIL'}")
    ok &= c2

    c3 = (n_alpha == "alpha" and len(d_alpha) == 400)
    checks.append(f"  parser extracts name+desc    : name={n_alpha!r} desclen={len(d_alpha)}  {'OK' if c3 else 'FAIL'}")
    ok &= c3

    c4 = (n_none == "" and d_none == "")
    checks.append(f"  no-frontmatter -> empty, no crash: {(n_none, d_none)}  {'OK' if c4 else 'FAIL'}")
    ok &= c4

    # BOTH STATES of the binding verdict:
    tiny_tokens = 10_000
    huge_tokens = 5_000_000
    _, v_nonbind, _ = binding(tiny_tokens, 1_000_000, 0.04)   # 10k vs 40k cap -> NON-BINDING
    _, v_bind, _ = binding(huge_tokens, 200_000, 0.04)        # 5M vs 8k cap -> BINDS
    c5 = (v_nonbind == "NON-BINDING")
    checks.append(f"  tiny listing / huge window   : {v_nonbind}  (expect NON-BINDING)  {'OK' if c5 else 'FAIL'}")
    ok &= c5
    c6 = (v_bind == "BINDS")
    checks.append(f"  huge listing / tiny window   : {v_bind}  (expect BINDS)  {'OK' if c6 else 'FAIL'}")
    ok &= c6

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    print("SELF-TEST (frontmatter parse + binding both-states proof):")
    print("\n".join(checks))
    if ok:
        print("\nSUCCESS:skill_listing_audit_selftest")
        return 0
    print("\nFAILED:skill_listing_audit_selftest one or more assertions failed")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="skill-listing truncation visibility")
    ap.add_argument("--local", action="append", default=None,
                    help="local skills root (repeatable); default ~/.claude/skills")
    ap.add_argument("--plugin", action="append", default=None,
                    help="plugin skills root (repeatable); default ~/.claude/plugins")
    ap.add_argument("--window", default="1000000,200000",
                    help="comma-list of context-window sizes to test the cap against")
    ap.add_argument("--fraction", type=float, default=0.04,
                    help="skillListingBudgetFraction to model (do NOT change the live setting)")
    ap.add_argument("--chars-per-token", type=float, default=4.0,
                    help="bytes-per-token estimate (estate heuristic = 4)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return run_selftest()

    local_roots = args.local or [DEF_LOCAL]
    plugin_roots = args.plugin or [DEF_PLUGIN]
    cpt = args.chars_per_token
    windows = [int(w) for w in str(args.window).split(",") if w.strip()]

    local_cnt = local_bytes = 0
    for r in local_roots:
        c, b = scan_root(r)
        local_cnt += c
        local_bytes += b
    plug_cnt = plug_bytes = 0
    for r in plugin_roots:
        c, b = scan_root(r)
        plug_cnt += c
        plug_bytes += b
    mir_cnt, mir_bytes = scan_root(DEF_MIRROR)

    local_tok = toks(local_bytes, cpt)
    plug_tok = toks(plug_bytes, cpt)
    total_cnt = local_cnt + plug_cnt
    total_bytes = local_bytes + plug_bytes
    total_tok = toks(total_bytes, cpt)

    print("SKILL-LISTING AUDIT")
    print(f"  local roots  : {local_roots}")
    print(f"  plugin roots : {plugin_roots}")
    print(f"  chars/token  : {cpt}   fraction modeled: {args.fraction}")
    print("\n-- COUNTS + name/description payload --")
    print(f"  LOCAL   SKILL.md : {local_cnt:>5}   name+desc bytes: {local_bytes:>9,}   ~tokens: {local_tok:>8,}")
    print(f"  PLUGIN  SKILL.md : {plug_cnt:>5}   name+desc bytes: {plug_bytes:>9,}   ~tokens: {plug_tok:>8,}")
    print(f"  TOTAL   SKILL.md : {total_cnt:>5}   name+desc bytes: {total_bytes:>9,}   ~tokens: {total_tok:>8,}")
    print(f"  (informational) authored mirror {DEF_MIRROR}: {mir_cnt} SKILL.md, "
          f"{mir_bytes:,} B - mirror of local, NOT added to the listing total)")

    print("\n-- DOES THE 0.04 CAP BIND? (listing tokens vs fraction*window) --")
    for w in windows:
        cap, v_local, d_local = binding(local_tok, w, args.fraction)
        _, v_total, d_total = binding(total_tok, w, args.fraction)
        print(f"  window {w:>9,} -> cap {cap:>7,} tok")
        print(f"     LOCAL-ONLY  ({local_tok:,} tok): {v_local:11}  (delta {d_local:+,} vs cap)")
        print(f"     LOCAL+PLUGIN ({total_tok:,} tok): {v_total:11}  (delta {d_total:+,} vs cap)")

    # Go/no-go summary
    print("\n-- GO / NO-GO --")
    for w in windows:
        cap = int(w * args.fraction)
        binds_total = total_tok > cap
        binds_local = local_tok > cap
        if binds_total and not binds_local:
            print(f"  @window {w:,}: plugin skills FLIP the cap from non-binding to BINDING. "
                  f"Listing is truncated by ~{total_tok - cap:,} tok; skills past the budget are dropped.")
        elif binds_total and binds_local:
            print(f"  @window {w:,}: cap BINDS even on local skills alone (over by {local_tok - cap:,} tok).")
        else:
            print(f"  @window {w:,}: cap NON-BINDING even with plugins ({cap - total_tok:,} tok headroom); "
                  f"lowering the fraction would only ADD truncation - no reason to lower it.")

    print("\nSUCCESS:skill_listing_audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
