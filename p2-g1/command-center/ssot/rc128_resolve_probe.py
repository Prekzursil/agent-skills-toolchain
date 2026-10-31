"""Which signal actually resolves an rc=128 row? Measure three, then pick -- do not guess.

CONTEXT. Fixing the rc=128 defect exposes 20 rows whose identity ancestry cannot decide.
My first resolution rule was `origin_match OR census>=0.5`, chosen on the reasoning that an
inclusive error only inflates a count while an exclusive one can drop a checkout holding the
only copy of something. Running it printed 12 rows where the two signals DISAGREED, and the
disagreements are not noise -- they are defect 2 from identity_by_ancestry.py's own docstring
reproduced inside its own fix:

    dsifry/metaswarm            census 95-96%   <- this repo VENDORS metaswarm
    Prekzursil/openmm-md-mcp    census 67%      <- this repo vendors its skill
    blader/humanizer            census 50%      <- likewise

A whole-tree blob census cannot separate "a checkout of this repo" from "a checkout of a
repo whose files this repo vendors". Folding those in would have published an inflated
count sourced from third-party repos. The disagreement print is what caught it; a rule that
silently collapsed to one side would have shipped.

So: measure a THIRD signal that a vendored copy cannot fake -- does the tree carry THIS
repo's own root-level identity (its top-level layout), which a vendored subtree or an
unrelated project does not. Then choose the rule from the measurement.

CONTROLS (both states, required before any row is believed):
  positive  a known checkout of this repo          -> markers PRESENT
  negative  the known metaswarm plugin clone       -> markers ABSENT
If those two do not separate, the marker test is inert and this script fails closed.

Read-only.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "rc128-resolve.json"

# Root-level paths that together identify THIS repo's own top level. A vendored copy of a
# third-party repo has its own root, not ours; a subtree copy carries the subtree, not these.
#
# The first version of this set was 5 entries weighted toward RECENT additions
# (REPO-TOPOLOGY.md, docs/ssot). Measured, that scored genuine but OLD checkouts at 1-2/5
# and would have dropped them: `work/agent-skills-toolchain-re`, whose own origin URL names
# this repo, has neither file. Widening to 10 long-lived top-level entries fixed the floor.
MARKERS = (
    "REPO-TOPOLOGY.md",
    "AGENTS.md",
    "command-center",
    "ci/tests",
    "docs/ssot",
    "skills",
    "hooks",
    "tools",
    ".github",
    "ruff.toml",
)
# Set BY THE CONTROL, not by fitting the rows. At MARKER_MIN=3 the both-states control
# FAILED: the known-vendored metaswarm clone scores 4/10 and would have been admitted. The
# threshold has to sit above the measured negative (4) and below the lowest true positive
# among the rows this test actually decides (6). Anything in 5..6 gives identical verdicts
# on this population; 5 is the low edge, so it is the least tuned choice in that band.
MARKER_MIN = 5

KNOWN_TOOLCHAIN = "C:/Users/Prekzursil/source/ast-integrate"
KNOWN_VENDORED = "C:/Users/Prekzursil/.claude/plugins/metaswarm"


def out(args: list[str], cwd: str) -> str:
    p = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.stdout.strip() if p.returncode == 0 else ""


def markers(path: str) -> dict:
    hits = [m for m in MARKERS if (Path(path) / m).exists()]
    return {"present": hits, "n": len(hits), "verdict": len(hits) >= MARKER_MIN}


def main() -> int:
    pos, neg = markers(KNOWN_TOOLCHAIN), markers(KNOWN_VENDORED)
    discriminates = pos["verdict"] and not neg["verdict"]
    n = len(MARKERS)
    print(f"CONTROL positive (real checkout)  : {pos['n']}/{n} {pos['present']}")
    print(f"CONTROL negative (vendored clone) : {neg['n']}/{n} {neg['present']}")
    print(f"discriminates: {discriminates}")
    if not discriminates:
        print("FAILED:rc128-resolve marker control did not discriminate")
        return 3

    # THIRD CONTROL, and the one that fixes the RULE ORDER rather than a threshold.
    # It asks whether markers could stand alone as the identity test. They cannot:
    # a genuine clone of this repo scores BELOW a vendored third-party clone.
    old_clone = markers("C:/Users/Prekzursil/work/agent-skills-toolchain-re")
    markers_standalone = old_clone["n"] > neg["n"]
    print(
        f"CONTROL genuine-but-old clone     : {old_clone['n']}/{n} "
        f"vs vendored {neg['n']}/{n} -> markers usable alone: {markers_standalone}"
    )
    print(
        "  => markers rank a real checkout below a vendored one, so ORIGIN stays primary\n"
        "     and markers only decide rows where there is no origin to appeal to."
    )

    rows = json.loads((HERE / "rc128-redproof.json").read_text(encoding="utf-8"))[
        "rc128_rows"
    ]
    census = {
        r["path"]: r["census_ratio"]
        for r in json.loads((HERE / "identity-by-ancestry.json").read_text("utf-8"))[
            "residual_rows"
        ]
    }

    resolved = []
    print(
        f"\n{'origin kind':<14}{'markers':<9}{'census':<8}{'VERDICT':<11}path",
    )
    for r in rows:
        origin = r["origin"]
        m = markers(r["path"])
        c = census.get(r["path"], 0.0)

        if not origin:
            kind = "absent"
            # No remote to appeal to: the marker test is the only identity signal left.
            verdict = m["verdict"]
        elif "agent-skills-toolchain" in origin:
            kind = "this-repo"
            verdict = True
        elif origin.startswith(("http", "git@", "ssh:")):
            kind = "other-remote"
            # AUTHORITATIVE negative. The census is known-misled here (vendoring), so it
            # does not get a vote. Residual disclosed in the report: a FORK of this repo
            # that re-pointed its origin would be misfiled by this branch.
            verdict = False
        else:
            kind = "local-path"
            # A --local clone of another checkout: resolve transitively through ITS origin.
            up = (
                out(["git", "remote", "get-url", "origin"], origin)
                if Path(origin).exists()
                else ""
            )
            verdict = (
                "agent-skills-toolchain" in up or "agent-skills-toolchain" in origin
            )
            kind = f"local->{'ours' if verdict else 'other'}"

        resolved.append(
            {
                "path": r["path"],
                "origin": origin,
                "origin_kind": kind,
                "is_shallow": r["is_shallow"] == "true",
                "markers": m["n"],
                "census_ratio": c,
                "is_checkout": bool(verdict),
                "census_would_say": c >= 0.5,
                "census_disagrees": bool(verdict) != (c >= 0.5),
            }
        )
        print(
            f"{kind:<14}{m['n']}/5      {c:<8.0%}{'CHECKOUT' if verdict else 'not-ours':<11}"
            f"{r['path'][:54]}"
        )

    yes = [r for r in resolved if r["is_checkout"]]
    disagree = [r for r in resolved if r["census_disagrees"]]
    print(f"\nrc=128 rows resolved as checkouts of this repo : {len(yes)}")
    print(f"rows where the census alone would have been wrong: {len(disagree)}")
    for r in disagree:
        print(
            f"    census {r['census_ratio']:.0%} said "
            f"{'ours' if r['census_would_say'] else 'not-ours'}, "
            f"origin/markers say {'ours' if r['is_checkout'] else 'not-ours'}: {r['path'][:48]}"
        )

    report = {
        "marker_set": list(MARKERS),
        "control": {
            "positive": pos,
            "negative": neg,
            "discriminates": discriminates,
            "genuine_but_old_clone": old_clone,
            "markers_usable_standalone": markers_standalone,
        },
        "rule": (
            "origin naming this repo -> checkout; origin naming another REMOTE -> not ours "
            "(authoritative: the blob census is misled by vendored trees); origin naming a "
            "LOCAL path -> resolve transitively; origin absent -> root-marker test."
        ),
        "residual": (
            "A fork of this repo whose origin was re-pointed at a different remote would be "
            "misfiled as not-ours. Not observed here. Settling experiment: for each "
            "other-remote row, fetch its origin and test whether OUR root commit is an "
            "ancestor of its HEAD in that store."
        ),
        "rows": resolved,
        "resolved_as_checkouts": [r["path"] for r in yes],
        "n_resolved_as_checkouts": len(yes),
        "n_census_would_be_wrong": len(disagree),
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nwrote {OUT}")
    print(f"SUCCESS:rc128-resolve checkouts={len(yes)} census_wrong_on={len(disagree)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
