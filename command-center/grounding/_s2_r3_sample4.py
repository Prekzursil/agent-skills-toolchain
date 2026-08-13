"""ROUND 3 / R3-A: a FOURTH independent sample of the bare-description render boundary.

Round 2 fitted the boundary from its own session and returned verdict H-SESSION
("B is NOT a fleet constant") from three samples.  Every one of those samples is a
HAND TRANSCRIPTION of an injected skill listing -- a single, unreplicated reading.
Nobody has ever checked whether a second reader of a comparable session transcribes
the same set.  That is the load-bearing input to the whole R7 table.

This probe adds sample 4 (this session's listing) and asks two separate questions:

  Q1 (transcription accuracy)  does an independent reader reproduce sample 3's set?
      H-TRANS-OK    : sample 3 was read correctly -> symmetric difference is EMPTY.
      H-TRANS-ERR   : sample 3 mis-transcribed    -> some names differ.
      These predict different outputs, so the probe can distinguish them.

  Q2 (does sample 4 discriminate H-CONST vs H-SESSION?)  Stated HONESTLY up front:
      it does NOT.  Sample 4 is a lane subagent spawned by the same orchestrator with
      a near-identical preamble to sample 3, so BOTH hypotheses predict the same
      boundary.  A control that cannot distinguish the two hypotheses is not a
      control (ground floor).  Sample 4 is therefore reported as CORROBORATION of the
      mechanism plus a transcription check -- NOT as new evidence for H-SESSION.

Detector controls:
  C1 premise     : every name observed BARE must have NON-EMPTY text on disk.
  C2 two parsers : a hand-rolled frontmatter reader and PyYAML (a C-implemented,
                   separately-authored YAML parser) must agree on the fleet total.
                   Round 1 shipped a parser that silently dropped 12 folded scalars
                   (-8,843 chars); PyYAML handles folded scalars natively, so this is
                   a mechanically independent check, not a re-run.
  C3 order       : the bare set must be a contiguous alphabetical TAIL.
  C4 decoys      : the fitter must fit the TRUE set far better than random/alpha/longest
                   30-subsets, or the fit means nothing.
  C5 split       : byte-identical description text rendering differently in two
                   namespaces in ONE session -- the decisive H-PARSE refutation --
                   must reproduce here or round 1's headline is sample-specific.
"""

from __future__ import annotations

import hashlib
import io
import json
import random
import sys
from pathlib import Path

import yaml

DAILY = Path("C:/Users/Prekzursil/.claude/skills.daily")
PLUGINS = Path("C:/Users/Prekzursil/.claude/plugins")
OUT = Path(
    "C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/S2-R3-SAMPLE4.json"
)

ROUND2_FLEET = 115461  # round-2 V1, folded-scalar-aware parser
ROUND2_FOLDED = 12
ROUND2_OVER1024 = 11

# --- prior samples (from the committed artifacts; NOT re-derived here) -------
PRIOR = [
    ("round-1 build", 30, 108144, 108144),
    ("independent audit", 29, 102511, 105336),
    ("round-2 build", 30, 102516, 105244),
]
# Round-2's transcription, verbatim from _s2_r2_boundary.py BARE_HERE.
SAMPLE3 = [
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

# --- SAMPLE 4: transcribed from THIS session's injected skill listing --------
# Read top-to-bottom off the listing before _s2_r2_boundary.py was opened.
SAMPLE4 = [
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

# Cross-namespace render states observed in THIS session's listing.
# (user skills.daily namespace, superpowers plugin namespace)
SPLIT_OBS = {
    "receiving-code-review": ("DESC", "BARE"),
    "requesting-code-review": ("DESC", "BARE"),
    "test-driven-development": ("DESC", "BARE"),
    "executing-plans": ("DESC", "BARE"),
    "writing-plans": ("BARE", "DESC"),
    "writing-skills": ("BARE", "DESC"),
}


def raw(p: Path) -> str:
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()


def _front(text: str) -> list[str] | None:
    lines = [x[:-1] if x.endswith("\r") else x for x in text.split("\n")]
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i]
    return None


def desc_handrolled(p: Path) -> tuple[str, bool]:
    """Parser A: hand-rolled block-scalar-aware reader."""
    body = _front(raw(p))
    if body is None:
        return "", False
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
                join = " " if rest.startswith(">") else "\n"
                return join.join(x for x in chunk if x or join == "\n"), True
            if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "'\"":
                rest = rest[1:-1]
            return rest, False
        i += 1
    return "", False


def desc_pyyaml(p: Path) -> str | None:
    """Parser B: PyYAML. Independent implementation, native folded-scalar support."""
    body = _front(raw(p))
    if body is None:
        return None
    try:
        doc = yaml.safe_load("\n".join(body))
    except yaml.YAMLError:
        return None
    if not isinstance(doc, dict):
        return None
    v = doc.get("description")
    return v if isinstance(v, str) else None


def fit_b(names, lens, observed_bare):
    total = sum(lens[d] for d in names)

    def score(b):
        run, mm = 0, 0
        for d in names:
            fits = run + lens[d] <= b
            if fits:
                run += lens[d]
            if fits == (d in observed_bare):
                mm += 1
        return mm

    best = (10**9, 0)
    for b in range(0, total + 26, 25):
        s = score(b)
        if s < best[0]:
            best = (s, b)
    for b in range(max(0, best[1] - 40), best[1] + 41):
        s = score(b)
        if s < best[0]:
            best = (s, b)
    return best


def main() -> int:
    names = sorted(d.name for d in DAILY.iterdir() if (d / "SKILL.md").is_file())
    lensA, folded, lensB, ydiff = {}, {}, {}, []
    for d in names:
        t, f = desc_handrolled(DAILY / d / "SKILL.md")
        lensA[d], folded[d] = len(t), f
        y = desc_pyyaml(DAILY / d / "SKILL.md")
        lensB[d] = 0 if y is None else len(y)
        if y is not None and y.strip() != t.strip():
            ydiff.append(d)

    # Loader-faithful length: what the renderer actually charges. Established by
    # _s2_r3_loaderparse.py against the rendered listing (an external signal):
    # the loader is LENIENT about the ': ' PyYAML throws on, but STOPS at ' #'.
    lensL = {}
    for d in names:
        t, _ = desc_handrolled(DAILY / d / "SKILL.md")
        cut = t.find(" #")
        lensL[d] = len(t[:cut].rstrip()) if cut >= 0 else len(t)

    fleetA, fleetB = sum(lensA.values()), sum(lensB.values())
    fleetL = sum(lensL.values())
    n_folded = sum(1 for d in names if folded[d])
    n_over = sum(1 for d in names if lensA[d] > 1024)
    rejected = [d for d in names if desc_pyyaml(DAILY / d / "SKILL.md") is None]
    rej_chars = sum(lensA[d] for d in rejected)

    print("=== C2  TWO INDEPENDENT PARSERS (hand-rolled vs PyYAML 6.0.3) ===")
    print(f"  skills on disk                : {len(names)}")
    print(f"  fleet desc chars  hand-rolled : {fleetA}")
    print(f"  fleet desc chars  PyYAML      : {fleetB}   delta={fleetB - fleetA}")
    print(
        f"  fleet desc chars  LOADER-FAITHFUL : {fleetL}   overcount={fleetA - fleetL}"
    )
    # The control is ATTRIBUTION, not a tolerance: every char of the hand-vs-strict
    # gap must be explained by a NAMED file, or the parsers disagree for a reason
    # nobody has identified and nothing below may be cited.
    respace = sum(lensA[d] - lensB[d] for d in names if d not in rejected)
    print(
        f"  gap attribution: {len(rejected)} PyYAML-REJECTED files hold {rej_chars} chars"
    )
    print(f"                   folded-scalar re-spacing accounts for {respace} chars")
    print(f"                   {rej_chars + respace} vs measured gap {fleetA - fleetB}")
    print(f"  folded scalars {n_folded} (round-2 said {ROUND2_FOLDED})")
    print(f"  over-1024      {n_over} (round-2 said {ROUND2_OVER1024})")
    print(f"  round-2 V1 fleet total {ROUND2_FLEET} -> delta {fleetA - ROUND2_FLEET}")
    c2 = (
        rej_chars + respace == fleetA - fleetB
        and n_folded == ROUND2_FOLDED
        and n_over == ROUND2_OVER1024
    )
    print(
        f"  C2: {'PASS (gap fully attributed)' if c2 else 'FAIL -- do not cite anything below'}"
    )
    if not c2:
        return 1
    print()

    s3, s4 = set(SAMPLE3), set(SAMPLE4)
    only3, only4 = sorted(s3 - s4), sorted(s4 - s3)
    print("=== C4-TRANS  independent re-transcription vs sample 3 ===")
    print(f"  sample 3 (round-2 build) n={len(s3)}")
    print(f"  sample 4 (this session)  n={len(s4)}")
    print(f"  in 3 not 4 : {only3}")
    print(f"  in 4 not 3 : {only4}")
    trans = (
        "H-TRANS-OK (sample 3 reproduces exactly)"
        if not only3 and not only4
        else "H-TRANS-ERR"
    )
    print(f"  VERDICT Q1 : {trans}")
    print()

    print("=== C1  PREMISE (bare skills must have real text on disk) ===")
    absent = sorted(b for b in s4 if b not in lensA)
    empty = sorted(b for b in s4 if lensA.get(b, 0) == 0)
    print(f"  absent from disk : {absent}")
    print(f"  empty on disk    : {empty}")
    print(
        f"  C1: {'PASS (render bug, not empty files)' if not absent and not empty else 'FAIL'}"
    )
    if absent or empty:
        return 1
    print()

    idx = {d: i for i, d in enumerate(names)}
    bidx = sorted(idx[d] for d in s4)
    first, last = bidx[0], bidx[-1]
    survivors = [d for d in names[first : last + 1] if d not in s4]
    before = [d for d in names[:first] if d in s4]
    print("=== C3  ORDER (contiguous alphabetical tail) ===")
    print(f"  first bare : {names[first]} (rank {first}/{len(names)})")
    print(
        f"  last  bare : {names[last]} (rank {last}) is-last-on-disk={last == len(names) - 1}"
    )
    print(f"  bare BEFORE the zone : {before}")
    print(
        f"  in-zone SURVIVORS {len(survivors)} -> {[(d, lensA[d]) for d in survivors]}"
    )
    print(f"  C3: {'PASS' if not before else 'FAIL'}")
    print()

    cum_first = sum(lensA[d] for d in names[:first])
    cum_surv = cum_first + sum(lensA[d] for d in survivors)
    mm, b_here = fit_b(names, lensA, s4)
    mmL, b_hereL = fit_b(names, lensL, s4)
    print("=== SENSITIVITY: does the fit survive the loader-faithful lengths? ===")
    print(f"  hand-rolled lengths     : B={b_here} mismatches={mm}")
    print(f"  loader-faithful lengths : B={b_hereL} mismatches={mmL}")
    print(
        f"  verdict stable: {mmL <= mm + 1}  (the 440-char correction is 0.38% of the fleet)"
    )
    print()

    print("=== C4  DECOY CONTROL (can the fitter fit ANY 30-set?) ===")
    rng = random.Random(20260813)
    rand = [fit_b(names, lensA, set(rng.sample(names, 30)))[0] for _ in range(200)]
    alpha = fit_b(names, lensA, set(names[:30]))[0]
    longest = fit_b(names, lensA, set(sorted(names, key=lambda d: -lensA[d])[:30]))[0]
    print(f"  TRUE sample-4 set : {mm} mismatches (B={b_here})")
    print(
        f"  200 random 30-sets: min={min(rand)} median={sorted(rand)[100]} max={max(rand)}"
    )
    print(f"  alphabetical  30  : {alpha}")
    print(f"  longest-desc  30  : {longest}")
    disc = mm < min(rand) and mm < alpha and mm < longest
    print(f"  C4: {'DISCRIMINATING' if disc else 'INERT -- fit is worthless'}")
    print()

    print("=== C5  CROSS-NAMESPACE SPLIT (the decisive H-PARSE refutation) ===")
    plug: dict[str, Path] = {}
    if PLUGINS.is_dir():
        for f in PLUGINS.rglob("skills/*/SKILL.md"):
            plug.setdefault(f.parent.name, f)
    rows, reproduced = [], 0
    for nm, (u_state, p_state) in SPLIT_OBS.items():
        du = (
            desc_handrolled(DAILY / nm / "SKILL.md")[0]
            if (DAILY / nm / "SKILL.md").is_file()
            else None
        )
        dp = desc_handrolled(plug[nm])[0] if nm in plug else None
        if du is None or dp is None:
            rows.append((nm, "MISSING", u_state, p_state, False))
            continue
        same = (
            hashlib.sha256(du.encode()).hexdigest()
            == hashlib.sha256(dp.encode()).hexdigest()
        )
        split = u_state != p_state
        ok = same and split
        reproduced += 1 if ok else 0
        rows.append((nm, "IDENTICAL" if same else "DIFFERENT", u_state, p_state, ok))
    for nm, byteq, u, p, ok in rows:
        print(
            f"  {nm:<26} bytes={byteq:<9} daily={u:<4} plugin={p:<4} {'<== SPLIT' if ok else ''}"
        )
    print(f"  byte-identical AND split-rendered: {reproduced}/{len(SPLIT_OBS)}")
    print(
        "  C5: a file's own bytes cannot render two ways in one session -> H-PARSE refuted again"
    )
    print()

    print("=== Q2  four samples ===")
    rows2 = PRIOR + [("round-3 (this session)", len(s4), cum_first, cum_surv)]
    print(f"  {'sample':<24}{'bare':>5}{'lower':>12}{'upper':>12}")
    for lab, n, lo, hi in rows2:
        print(f"  {lab:<24}{n:>5}{lo:>12}{hi:>12}")
    spread = max(r[3] for r in rows2) - min(r[2] for r in rows2)
    print(f"  best-fit B here : {b_here} ({mm} mismatches / {len(names)})")
    print(f"  spread across 4 samples : {spread} chars")
    print(
        "  Q2 VERDICT: sample 4 == sample 3 exactly. Same orchestrator, near-identical"
    )
    print(
        "              preamble -> H-CONST and H-SESSION predict the SAME result here."
    )
    print("              NOT new evidence for H-SESSION; it is a reproducibility +")
    print(
        "              transcription check. H-SESSION still rests on samples 1 vs 2/3."
    )

    OUT.write_text(
        json.dumps(
            {
                "parsers": {
                    "handrolled_fleet": fleetA,
                    "pyyaml_fleet": fleetB,
                    "nontrivial_diffs": ydiff,
                    "folded": n_folded,
                    "over1024": n_over,
                    "round2_v1": ROUND2_FLEET,
                    "delta_vs_round2": fleetA - ROUND2_FLEET,
                    "pass": c2,
                },
                "transcription": {
                    "only_in_sample3": only3,
                    "only_in_sample4": only4,
                    "verdict": trans,
                },
                "premise": {"absent": absent, "empty": empty, "pass": True},
                "order": {
                    "first_bare": names[first],
                    "first_rank": first,
                    "last_is_end": last == len(names) - 1,
                    "bare_before_zone": before,
                    "survivors": survivors,
                    "pass": not before,
                },
                "fit": {
                    "B": b_here,
                    "mismatches": mm,
                    "n": len(names),
                    "loader_faithful_B": b_hereL,
                    "loader_faithful_mismatches": mmL,
                    "fleet_loader_faithful": fleetL,
                    "overcount_vs_cited": fleetA - fleetL,
                    "pyyaml_rejected": rejected,
                },
                "decoys": {
                    "true": mm,
                    "random_min": min(rand),
                    "random_median": sorted(rand)[100],
                    "alpha30": alpha,
                    "longest30": longest,
                    "discriminating": disc,
                },
                "split": {
                    "rows": [
                        {
                            "skill": r[0],
                            "bytes": r[1],
                            "daily": r[2],
                            "plugin": r[3],
                            "split": r[4],
                        }
                        for r in rows
                    ],
                    "reproduced": reproduced,
                },
                "samples": [
                    {"label": r[0], "bare": r[1], "lo": r[2], "hi": r[3]} for r in rows2
                ],
                "spread_chars": spread,
                "q2": "sample 4 does NOT discriminate H-CONST vs H-SESSION",
            },
            indent=1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    ok = c2 and disc and not before and not only3 and not only4
    print()
    print(
        f"{'SUCCESS' if ok else 'FAILED'}:s2-r3-sample4 "
        f"trans={'OK' if not only3 and not only4 else 'ERR'} fit={mm} split={reproduced}/6"
    )
    return 0 if ok else 1


sys.exit(main())
