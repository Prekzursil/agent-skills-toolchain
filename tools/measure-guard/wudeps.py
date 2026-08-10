"""Gate the 2,007 work-unit dependencies that nothing currently validates.

THE GAP THIS CLOSES. `tools/command-center/validate.py` does not contain the string `work_units`.
It validates the 103 register `items` -- reachability, dispositions, the register snapshot hash --
and never looks at the 2,007 work units, which are the actual program. Measured 2026-08-11 against
`command-center/WORK-UNIT-CATALOG.json`:

    41  dependency refs resolve to no unit and are not buckets  (ARC 19, WFA 17, CC 4, IMP 1)
    876 dependency refs point at a bucket with ZERO members     (B07 alone carries 297)
    0   cycles, 0 self-dependencies                             (both RECORDED as present; fixed)

The catalog's own `work_units_meta.known_defects_at_merge` is the only thing that has ever recorded
any of this, and four of its seven entries are wrong or stale:

    unknown_form_dependency_tokens  ['BKT-ARC','BKT-CMD','BKT-IMP','WFA-1of2']  <- none of these
                                    exist; the real tokens are bare ARC/WFA/CC/IMP. Right COUNT,
                                    fictional CONTENT.
    dependency_cycles      1        <- measured 0 (control: a synthetic 2-cycle IS detected)
    self_dependencies      3 ids    <- measured none; all three now point at IMP-0265/IMP-0264
    zero-member buckets    (absent) <- 876 edges, never recorded at all

WHY A RATCHET AND NOT A HARD FAIL. 917 findings are pre-existing. A gate that fails on all of them
either blocks every unrelated PR or gets deleted within a week. This freezes the measured counts and
fails only on REGRESSION, which is the line that can actually be held. Improvements are reported so
the floor gets lowered rather than silently drifting into slack -- an unreported improvement is how
a ratchet stops ratcheting.

WHAT THIS GATE DELIBERATELY DOES NOT DECIDE. Whether a `B\\d+` dependency is *satisfiable* is not
knowable here: the token `bucket` is undefined in the catalog's `contract`, `defaults` and
`tool_policy`, and appears twice in the 29,273-line governing spec, neither time as a definition
(control: `phase` appears 172 times there). So this reports zero-member bucket references as a
STRUCTURAL fact -- N edges point at a set with no members -- and takes no position on whether that
blocks execution. That reading is an owner call.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"

BUCKET_TOKEN = re.compile(r"B\d+")

#: Below this, assume the read broke rather than that the program shrank.
MIN_UNITS = 1500

#: Measured at 2026-08-11. Lower these when the count genuinely improves; never raise them to make
#: a red gate green -- that is the one edit this file exists to prevent.
BASELINE = {
    "dangling_refs": 41,
    "zero_member_bucket_refs": 876,
    "cycles": 0,
    "self_dependencies": 0,
}


def load(path: Path | None = None) -> dict:
    return json.loads((path or CATALOG).read_text(encoding="utf-8"))


def scan(catalog: dict) -> dict:
    units = catalog.get("work_units") or []
    if len(units) < 1:
        raise ValueError("catalog holds no work_units (fail closed)")

    ids = {u["id"] for u in units}
    members: dict[str, int] = {}
    for unit in units:
        bucket = unit.get("bucket")
        if isinstance(bucket, str) and BUCKET_TOKEN.fullmatch(bucket):
            members[bucket] = members.get(bucket, 0) + 1

    dangling: list[tuple[str, str]] = []
    zero_bucket: list[tuple[str, str]] = []
    self_deps: list[str] = []
    graph: dict[str, list[str]] = {}

    for unit in units:
        uid = unit["id"]
        deps = unit.get("dependencies") or []
        graph[uid] = [d for d in deps if d in ids and d != uid]
        for dep in deps:
            if dep == uid:
                self_deps.append(uid)
            elif BUCKET_TOKEN.fullmatch(dep):
                members.setdefault(dep, 0)
                if members[dep] == 0:
                    zero_bucket.append((uid, dep))
            elif dep not in ids:
                dangling.append((uid, dep))

    return {
        "units_scanned": len(units),
        "dangling_refs": dangling,
        "zero_member_bucket_refs": zero_bucket,
        "self_dependencies": sorted(set(self_deps)),
        "cycles": _cycles(graph),
        "bucket_members": members,
    }


def _cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Every back-edge found by an iterative DFS. Iterative because 2,007 nodes overflow the
    default recursion limit on a deep chain, and raising the limit to hide that is a crash waiting
    for a bigger catalog."""
    WHITE, GREY, BLACK = 0, 1, 2
    colour = dict.fromkeys(graph, WHITE)
    found: list[list[str]] = []
    for root in graph:
        if colour[root] != WHITE:
            continue
        stack: list[tuple[str, int]] = [(root, 0)]
        path: list[str] = []
        colour[root] = GREY
        path.append(root)
        while stack:
            node, i = stack[-1]
            if i < len(graph.get(node, [])):
                stack[-1] = (node, i + 1)
                nxt = graph[node][i]
                if colour.get(nxt) == GREY:
                    found.append(path[path.index(nxt) :] + [nxt])
                elif colour.get(nxt) == WHITE:
                    colour[nxt] = GREY
                    path.append(nxt)
                    stack.append((nxt, 0))
            else:
                colour[node] = BLACK
                stack.pop()
                if path:
                    path.pop()
    return found


def _counts(report: dict) -> dict[str, int]:
    return {k: len(report[k]) for k in BASELINE}


def regressions(report: dict, baseline: dict[str, int] | None = None) -> list[str]:
    base = baseline if baseline is not None else BASELINE
    now = _counts(report)
    return [
        f"{k}: {now[k]} > baseline {base[k]} (+{now[k] - base[k]})"
        for k in base
        if now[k] > base[k]
    ]


def improvements(report: dict, baseline: dict[str, int] | None = None) -> list[str]:
    base = baseline if baseline is not None else BASELINE
    now = _counts(report)
    return [
        f"{k}: {now[k]} < baseline {base[k]} -- lower the baseline to {now[k]}"
        for k in base
        if now[k] < base[k]
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = scan(load())
    except (OSError, ValueError) as exc:
        print(f"FAILED:wudeps {exc}")
        return 1

    if args.json:
        printable = {k: v for k, v in report.items() if k != "bucket_members"}
        print(
            json.dumps(
                {**printable, "bucket_members": report["bucket_members"]},
                indent=2,
                default=list,
            )
        )

    # Fail closed on a collapsed read BEFORE reporting anything, so "0 findings" can never come
    # from having scanned nothing.
    if report["units_scanned"] < MIN_UNITS:
        print(
            f"FAILED:wudeps only {report['units_scanned']} work units read, below the floor of "
            f"{MIN_UNITS}; the read has probably broken rather than the program shrunk"
        )
        return 1

    counts = _counts(report)
    print(
        f"  units={report['units_scanned']}  dangling={counts['dangling_refs']}  "
        f"zero-member-bucket-refs={counts['zero_member_bucket_refs']}  "
        f"cycles={counts['cycles']}  self-deps={counts['self_dependencies']}"
    )
    empty = sorted(b for b, n in report["bucket_members"].items() if n == 0)
    if empty:
        print(f"  buckets with zero members: {', '.join(empty)}")

    for line in improvements(report):
        print(f"  IMPROVED {line}")
    bad = regressions(report)
    for line in bad:
        print(f"  REGRESSED {line}")
    if bad:
        print(f"FAILED:wudeps {len(bad)} metric(s) worse than the recorded baseline")
        return 1
    print(
        "SUCCESS:wudeps no work-unit dependency metric regressed against the baseline"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main(sys.argv[1:]))
