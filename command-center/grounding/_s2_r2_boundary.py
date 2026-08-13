"""ROUND 2 / R7: a FOURTH independent sample of the render boundary.

The round-1 build fitted B=108,144 from its own session and wrote
"the fleet is ~7,300 chars OVER -- that is the entire defect" as if B were a
fleet CONSTANT.  The audit refuted that with its own session (boundary 13
skills earlier).  This probe adds a third measurement -- THIS session's
injected skill listing, transcribed below -- and asks whether B is stable.

Two hypotheses, stated BEFORE the control runs (rule 3c):
  H-CONST   : B is a property of the harness -> all three sessions should put
              the boundary at the same cumulative-char position (within noise).
  H-SESSION : B varies with what else is in the prompt -> the three boundaries
              should be spread by materially more than one skill's description.
They predict DIFFERENT outputs, so this probe can distinguish them.

Detector controls:
  C1 premise  : every name observed BARE must have NON-EMPTY description text on
                disk.  A break would mean the render bug premise itself is wrong.
  C2 parser   : must independently reproduce three constants computed by two
                earlier, separately-written parsers -- fleet total 115456,
                folded-scalar count 12, over-1024 count 11.  The round-1 builder
                caught a parser of their own that silently dropped the 12 folded
                descriptions (~8,865 chars); this is the guard against that.
  C3 ordering : the bare set must be a contiguous alphabetical TAIL (allowing
                in-zone survivors).  Bare entries BEFORE the zone would refute
                order-truncation and this probe would have to report that.
"""

import io
import json
import os
import sys

DAILY = "C:/Users/Prekzursil/.claude/skills.daily"
REPO = "C:/Users/Prekzursil/source/ast-integrate"

# Constants computed by two earlier independently-written parsers
# (_s2_appendonly_and_negcase.py post-edit, and _audit_s2_negcase.py).
EXPECT_FLEET = 115456
EXPECT_FOLDED = 12
EXPECT_OVER1024 = 11

BUILDER_B = 108144  # round-1 fit, observation B
BUILDER_BARE_N = 30
AUDIT_CUM_FIRST_BARE = 102511
AUDIT_CUM_INCL_SURV = 105336
AUDIT_BARE_N = 29

# --- Observation: skills rendering with NO description in THIS session ---
# Transcribed from this session's own injected skill listing.  Differs from the
# auditor's sample by exactly one entry (writing-skills), which is the point.
BARE_HERE = [
    "ui-drive",
    "ui-invariant-walk",
    "use-image-clipboard",
    "using-git-worktrees",
    "vercel-deploy",
    "verification-before-completion",
    "verification-loop",
    "video-convert",
    "video-join-concat",
    "video-resize-aspect",
    "video-stabilize",
    "voice-analyze",
    "voice-apply",
    "voice-blend",
    "voice-create",
    "volatility-3",
    "webapp-testing",
    "windbg-command-cookbook",
    "windbg-preview",
    "windows-virtualization-conflict-triage",
    "winui-app",
    "workflow-foundry",
    "workflow-monitor",
    "writing-plans",
    "writing-skills",
    "wsl-vmware-cutover",
    "x-api",
    "x64dbg",
    "yeet",
    "zero-issue-coding",
]


def read_raw(p):
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()


def desc_of(path):
    """Frontmatter description; folded/literal block scalars included."""
    text = read_raw(path)
    lines = [x[:-1] if x.endswith("\r") else x for x in text.split("\n")]
    if not lines or lines[0].strip() != "---":
        return "", False
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return "", False
    body = lines[1:end]
    i = 0
    while i < len(body):
        ln = body[i]
        if ln.startswith("description:"):
            rest = ln.partition(":")[2].strip()
            if rest in (">", ">-", "|", "|-", ">+", "|+"):
                i += 1
                chunk = []
                while i < len(body) and (
                    body[i].strip() == "" or body[i][:1] in (" ", "\t")
                ):
                    chunk.append(body[i].strip())
                    i += 1
                joiner = " " if rest.startswith(">") else "\n"
                return joiner.join(x for x in chunk if x or joiner == "\n"), True
            if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "'\"":
                rest = rest[1:-1]
            return rest, False
        i += 1
    return "", False


def fit_b(names, lens, observed_bare):
    """Greedy walk; find B minimising mismatches against observed_bare."""
    best = (10**9, None)
    total = sum(lens[d] for d in names)

    # coarse 25-char sweep, then a +-40 fine sweep around the coarse minimum
    def score(b):
        run = 0
        mm = 0
        for d in names:
            fits = run + lens[d] <= b
            if fits:
                run += lens[d]
            if fits == (
                d in observed_bare
            ):  # rendered-but-observed-bare, or vice versa
                mm += 1
        return mm

    for b in range(0, total + 26, 25):
        s = score(b)
        if s < best[0]:
            best = (s, b)
    lo = max(0, best[1] - 40)
    for b in range(lo, best[1] + 41):
        s = score(b)
        if s < best[0]:
            best = (s, b)
    return best[0], best[1]


def main():
    names = [
        d
        for d in sorted(os.listdir(DAILY))
        if os.path.isfile(os.path.join(DAILY, d, "SKILL.md"))
    ]
    lens, folded = {}, {}
    for d in names:
        t, f = desc_of(os.path.join(DAILY, d, "SKILL.md"))
        lens[d] = len(t)
        folded[d] = f

    fleet = sum(lens.values())
    n_folded = sum(1 for d in names if folded[d])
    n_over = sum(1 for d in names if lens[d] > 1024)

    print("=== C2 PARSER CONTROL (must reproduce 3 constants from 2 other parsers) ===")
    ok2 = True
    for label, got, want in (
        ("fleet desc chars", fleet, EXPECT_FLEET),
        ("folded scalars", n_folded, EXPECT_FOLDED),
        ("descriptions > 1024", n_over, EXPECT_OVER1024),
    ):
        good = got == want
        ok2 &= good
        print(
            "  %-22s got=%-8d want=%-8d %s"
            % (label, got, want, "OK" if good else "MISMATCH")
        )
    print("  parser control:", "PASS" if ok2 else "FAIL -- do not cite anything below")
    if not ok2:
        return 1
    print()

    bare = set(BARE_HERE)
    print("=== C1 PREMISE CONTROL (bare skills must have real text on disk) ===")
    absent = sorted(b for b in bare if b not in lens)
    empty = sorted(b for b in bare if lens.get(b, 0) == 0)
    print("  observed bare this session :", len(bare))
    print("  absent from disk           :", absent)
    print("  present but EMPTY on disk  :", empty)
    print(
        "  premise control:",
        "PASS (render bug, not empty files)" if not absent and not empty else "FAIL",
    )
    if absent or empty:
        return 1
    print()

    idx = {d: i for i, d in enumerate(names)}
    bidx = sorted(idx[d] for d in bare)
    first, last = bidx[0], bidx[-1]
    survivors = [d for d in names[first : last + 1] if d not in bare]
    before = [d for d in names[:first] if d in bare]

    print("=== C3 ORDER CONTROL ===")
    print("  first bare : %s (rank %d/%d)" % (names[first], first, len(names)))
    print(
        "  last  bare : %s (rank %d)  is-last-on-disk=%s"
        % (names[last], last, last == len(names) - 1)
    )
    print("  bare BEFORE the zone (would refute order-truncation):", before)
    print("  in-zone SURVIVORS %d -> %s" % (len(survivors), survivors))
    print("  survivor desc lengths:", [(d, lens[d]) for d in survivors])
    print("  order control:", "PASS (contiguous tail)" if not before else "FAIL")
    print()

    cum_first = sum(lens[d] for d in names[:first])
    cum_surv = cum_first + sum(lens[d] for d in survivors)
    mm, b_here = fit_b(names, lens, bare)
    cross = None
    run = 0
    for d in names:
        run += lens[d]
        if cross is None and run > BUILDER_B:
            cross = d

    print("=== R7  THREE SESSIONS, ONE QUESTION: is B a constant? ===")
    rows = [
        ("round-1 build (obs B)", BUILDER_BARE_N, BUILDER_B, BUILDER_B),
        ("independent audit", AUDIT_BARE_N, AUDIT_CUM_FIRST_BARE, AUDIT_CUM_INCL_SURV),
        ("THIS session (round 2)", len(bare), cum_first, cum_surv),
    ]
    print("  %-24s %5s %12s %12s" % ("sample", "bare", "lower-bound", "upper-bound"))
    for lab, n, lo, hi in rows:
        print("  %-24s %5d %12d %12d" % (lab, n, lo, hi))
    los = [r[2] for r in rows]
    his = [r[3] for r in rows]
    spread = max(his) - min(los)
    print()
    print(
        "  best-fit B for THIS session : %d  (mismatches %d/%d)"
        % (b_here, mm, len(names))
    )
    print(
        "  builder B crosses at        : %s (rank %d) vs first-bare %s (rank %d) -> %d skills apart"
        % (cross, idx[cross], names[first], first, abs(idx[cross] - first))
    )
    print("  spread across the 3 samples : %d chars" % spread)
    print(
        "  one median description      : 263 chars  -> spread = %.1f median descriptions"
        % (spread / 263.0)
    )
    print()
    verdict = "H-SESSION (B is NOT a fleet constant)" if spread > 2 * 263 else "H-CONST"
    print("  VERDICT:", verdict)
    print(
        "  bare COUNT per session      : %d / %d / %d  (also not constant)"
        % (BUILDER_BARE_N, AUDIT_BARE_N, len(bare))
    )
    print()

    print("=== R2  the '26% of the need' denominator, recomputed per sample ===")
    over_chars = sum(lens[d] for d in names if lens[d] > 1024)
    freed = over_chars - 1024 * n_over
    print(
        "  11 over-spec descriptions hold %d chars; capping at 1024 frees %d"
        % (over_chars, freed)
    )
    for lab, _n, lo, hi in rows:
        need_hi = fleet - lo
        need_lo = fleet - hi
        print(
            "  %-24s need %d..%d chars -> capping covers %.0f%%..%.0f%%"
            % (
                lab,
                need_lo,
                need_hi,
                100.0 * freed / need_hi,
                100.0 * freed / max(need_lo, 1),
            )
        )

    out = {
        "parser_control": {
            "fleet": fleet,
            "folded": n_folded,
            "over1024": n_over,
            "pass": True,
        },
        "premise_control": {"absent": absent, "empty": empty, "pass": True},
        "order_control": {
            "first_bare": names[first],
            "first_rank": first,
            "last_is_end": last == len(names) - 1,
            "bare_before_zone": before,
            "survivors": survivors,
            "pass": not before,
        },
        "this_session": {
            "bare_n": len(bare),
            "cum_to_first_bare": cum_first,
            "cum_incl_survivors": cum_surv,
            "best_fit_B": b_here,
            "mismatches": mm,
        },
        "three_samples": [
            {"label": r[0], "bare": r[1], "lo": r[2], "hi": r[3]} for r in rows
        ],
        "spread_chars": spread,
        "verdict": verdict,
        "fleet_total": fleet,
        "cap_frees": freed,
    }
    with io.open(
        REPO + "/command-center/grounding/S2-R2-BOUNDARY.json",
        "w",
        encoding="utf-8",
        newline="\n",
    ) as f:
        f.write(json.dumps(out, indent=1))
    print()
    print("SUCCESS:s2-r2-boundary spread=%d verdict=%s" % (spread, verdict.split()[0]))
    return 0


sys.exit(main())
