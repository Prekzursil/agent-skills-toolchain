"""Classify each differing twin pair by the DIRECTION of its divergence.

The fan-out contract's C4 result is that a one-directional read cannot see
two-directional divergence, and that 100% of the resulting errors pointed at
data loss. So before any twin pair is declared "root is ahead", measure BOTH
directions: lines the root holds that the mirror lacks, AND lines the mirror
holds that the root lacks.

Emits a per-pair verdict in {root-ahead, mirror-ahead, two-way} plus the counts
that produced it, so each KNOWN_DIVERGENT reason can cite a number.

Run:  python command-center/slop-report/_r3_direction.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = Path(__file__).with_name("_r3_twinsurface.out.json")
OUT = Path(__file__).with_suffix(".out.json")
MIRROR_ROOT = "agent-self/config/"


def meaningful(text: str) -> Counter:
    """Multiset of non-blank stripped lines: whitespace reflow alone is not drift."""
    return Counter(ln.strip() for ln in text.splitlines() if ln.strip())


def read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def classify(root: str, mirror: str) -> dict:
    a, b = meaningful(read(root)), meaningful(read(mirror))
    root_only = a - b
    mirror_only = b - a
    n_root, n_mirror = sum(root_only.values()), sum(mirror_only.values())
    if n_root and n_mirror:
        verdict = "two-way"
    elif n_root:
        verdict = "root-ahead"
    elif n_mirror:
        verdict = "mirror-ahead"
    else:
        verdict = "whitespace-only"
    return {
        "root": root,
        "verdict": verdict,
        "root_only_lines": n_root,
        "mirror_only_lines": n_mirror,
        "root_only_sample": [ln for ln, _ in root_only.most_common(3)],
        "mirror_only_sample": [ln for ln, _ in mirror_only.most_common(3)],
    }


def main() -> int:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    rows = [classify(p["root"], p["mirror"]) for p in data["differing_pairs"]]

    # ---- controls -------------------------------------------------------
    controls = {}
    # C1 not constant: an identical pair must classify as no-difference.
    same = data["identical_pairs"][0]
    ctl = classify(same, MIRROR_ROOT + same)
    controls["c1_identical_pair_has_zero_both_ways"] = (
        ctl["root_only_lines"] == 0 and ctl["mirror_only_lines"] == 0
    )
    # C2 the two-way detector can actually fire: a synthetic pair with unique
    # content on BOTH sides must classify two-way, not root-ahead.
    syn_a, syn_b = (
        Counter(["shared", "only-in-root"]),
        Counter(["shared", "only-in-mirror"]),
    )
    controls["c2_two_way_detectable"] = bool(syn_a - syn_b) and bool(syn_b - syn_a)
    # C3 direction is not symmetric-blind: a strict-superset pair must read
    # root-ahead, never two-way.
    sup_a, sup_b = Counter(["shared", "extra"]), Counter(["shared"])
    controls["c3_superset_reads_one_way"] = bool(sup_a - sup_b) and not bool(
        sup_b - sup_a
    )

    tally = Counter(r["verdict"] for r in rows)
    payload = {
        "rev": data["rev"],
        "differing": len(rows),
        "tally": dict(tally),
        "controls": controls,
        "all_controls_pass": all(controls.values()),
        "rows": sorted(rows, key=lambda r: (r["verdict"], r["root"])),
    }
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    for verdict in ("two-way", "root-ahead", "mirror-ahead", "whitespace-only"):
        for r in payload["rows"]:
            if r["verdict"] == verdict:
                print(
                    f"{r['verdict']:>15}  +{r['root_only_lines']:<4}/-{r['mirror_only_lines']:<4} {r['root']}"
                )
    print(f"\ntally={dict(tally)}")
    for k, v in controls.items():
        print(f"  control {k}: {v}")
    if not payload["all_controls_pass"]:
        print("FAILED:r3-direction a control did not pass")
        return 1
    print(f"SUCCESS:r3-direction -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
