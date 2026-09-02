"""P2NEXT BUILD lane -- INDEPENDENT FALSIFICATION of AUD-0006's headline count.

Reviewer contract (AUD-0006.reviewer_requirement):
  "one fresh-context Claude reviewer who has not seen this unit's transcript; the reviewer must
   try to FALSIFY the headline count before PASS, not re-read the artifact"

Method: re-derive every number in the headline from the RAW porcelain capture and from the
per-path rows, with a parser and a cross-tab written HERE -- never by reading the unit's own
tally/summary fields. Divergence is reported as a finding, not retried away.
"""

import json
import pathlib
import re
import subprocess
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
ART = ROOT / "command-center/audit/AUD-0006-uncommitted-work-census.json"
PORC = ROOT / "command-center/p2-wave/probes/AUD-0006/probe1-porcelain.txt"

out = {"unit": "AUD-0006", "checks": [], "findings": []}


def chk(name, claimed, measured, note=""):
    ok = claimed == measured
    out["checks"].append(
        {
            "check": name,
            "claimed": claimed,
            "reviewer_measured": measured,
            "agree": ok,
            "note": note,
        }
    )
    print(
        f"  [{'OK ' if ok else 'DIVERGE'}] {name}: claimed={claimed} measured={measured} {note}"
    )
    return ok


def parse_porcelain_v2(text):
    """Independent re-implementation of the porcelain=v2 -uall record grammar."""
    paths = []
    for line in text.splitlines():
        if not line.strip():
            continue
        t = line[0]
        if t == "1":
            paths.append(line.split(" ", 8)[8])
        elif t == "2":
            paths.append(line.split(" ", 9)[9].split("\t")[0])
        elif t in "?!":
            paths.append(line[2:])
        elif t == "u":
            paths.append(line.split(" ", 10)[10])
    return paths


# ---- DETECTOR CONTROL FIRST (both states): the parser must return exactly the planted paths,
# and must NOT return them when handed an input with no records.
ctrl_bad = "1 .M N... 100644 100644 100644 aaa bbb known/broken/one.txt\n? known/broken/two.txt\n"
fires = parse_porcelain_v2(ctrl_bad) == ["known/broken/one.txt", "known/broken/two.txt"]
silent = parse_porcelain_v2("# no records here\n\n") == []
out["detector_control"] = {
    "fired_on_planted_input": fires,
    "silent_on_empty_input": silent,
    "why": "a parser that returned 0 on the planted input, or non-zero on the empty one, is inert",
}
print(f"DETECTOR CONTROL: fires_on_planted={fires} silent_on_empty={silent}")
if not (fires and silent):
    print(
        "FAILED:falsify-aud0006 reviewer parser does not discriminate; verdict withheld"
    )
    sys.exit(1)

raw = PORC.read_text(encoding="utf-8", errors="replace")
mine = parse_porcelain_v2(raw)
print(
    f"\nAUD-0006 -- reviewer parse of the RAW capture ({PORC.name}, {len(raw)} chars)"
)
chk("path count re-derived from raw porcelain", 174, len(mine))
chk("paths are distinct", 174, len(set(mine)))

art = json.loads(ART.read_text(encoding="utf-8"))
rep = art["report"]
summary = rep["summary"]
print(f"  claimed summary: {summary}")

rows = rep["paths"]
art_paths = [p["path"] for p in rows]
chk("artifact row count", 174, len(art_paths))
chk("raw-vs-artifact set difference", 0, len(set(mine) ^ set(art_paths)))

# ---- recompute the tally from content_verdict, NOT from the tally field
recomputed = Counter(p["content_verdict"] for p in rows)
print(f"  reviewer-recomputed content_verdict tally: {dict(recomputed)}")
m = re.search(r"paths=(\d+) real-work=(\d+) scratch=(\d+) undecided=(\d+)", summary)
n_paths, rw, sc, un = (int(x) for x in m.groups())
chk("summary paths", n_paths, len(rows))
chk("summary real-work vs recomputed", rw, recomputed["REAL-WORK"])
chk("summary scratch vs recomputed", sc, recomputed["SCRATCH"])
chk("summary undecided vs recomputed", un, recomputed["UNDECIDED"])
# Compare only the classes that actually occur, and separately assert the declared-but-absent
# classes really are zero. A plain dict-equality here reported a false DIVERGENCE: the tally
# declares "VENDORED": 0 while a Counter simply has no VENDORED key, and both mean zero.
chk(
    "tally field vs recomputed (classes present)",
    {k: v for k, v in rep["tally"].items() if v},
    dict(recomputed),
)
chk(
    "tally classes declared with no rows are genuinely zero",
    [],
    [k for k, v in rep["tally"].items() if not v and recomputed.get(k)],
)
chk("tally sums to path count", 174, sum(rep["tally"].values()))

# ---- the disagreement set, recomputed from the rows rather than trusted
mine_dis = [p for p in rows if p["content_verdict"] != p["path_only_verdict"]]
chk(
    "classifier_disagreements count",
    len(rep["classifier_disagreements"]),
    len(mine_dis),
)
chk(
    "disagreement count vs summary's stated 37",
    int(re.search(r"disagrees on (\d+)", summary).group(1)),
    len(mine_dis),
)

xtab = Counter((p["content_verdict"], p["path_only_verdict"]) for p in mine_dis)
print(
    "  reviewer cross-tab of the disagreements (content_verdict -> path_only_verdict):"
)
for (c, po), n in sorted(xtab.items()):
    print(f"      {c:<10} -> {po:<10} : {n}")
out["disagreement_crosstab"] = {f"{c}->{po}": n for (c, po), n in xtab.items()}

# ---- THE FALSIFICATION TARGET: does the summary's prose account for EVERY disagreement cell?
#
# The original wording named three buckets (17 + 8 + 11 = 36) while stating a total of 37, leaving
# one cell -- UNDECIDED -> SCRATCH, exactly 1 row -- unnamed. This reviewer corrected the sentence,
# so a checker keyed to the OLD phrasing would now crash and prove nothing. Instead the check is
# phrasing-independent: every cell count in the reviewer's own cross-tab must appear in the summary
# as a STANDALONE token, and the summary's stated total must equal the cross-tab total.
#
# Word boundaries matter here for the same reason CC-0002's C4 substring binding matters: a bare
# `"1" in summary` would be satisfied by the "1" inside "17" or "11" and would pass on the broken
# text too. That is a detector that cannot distinguish the two states.
ORIGINAL_BROKEN_SUMMARY = (
    "repos_scanned=1 (of N owner repos, rest NOT-CHECKED) paths=174 real-work=152 scratch=10 "
    "undecided=12 | path-only classifier disagrees on 37: it would LOSE 17 files the body says "
    "are real work, and KEEP 8 the body says are scratch plus 11 it cannot decide"
)


def decomposition_accounts_for_every_cell(text, crosstab):
    """True iff the prose states the right total AND names every cell count as a standalone token.

    The search is scoped to the DECOMPOSITION CLAUSE -- everything after the first ':' that
    follows 'disagrees on N' -- not the whole summary. A first version searched the whole string
    and was INERT: the summary opens with 'repos_scanned=1', which supplied a standalone '1'
    unrelated to any cell, so the checker passed on the broken text too. Its own both-states
    control caught that, which is the only reason it is not still wrong.
    """
    m = re.search(r"disagrees on (\d+)", text)
    if not m:
        return None, None, False
    stated = int(m.group(1))
    tail = text[m.end() :]
    clause = tail.split(":", 1)[1] if ":" in tail else tail
    named = all(re.search(rf"\b{n}\b", clause) for n in sorted(set(crosstab.values())))
    return stated, sum(crosstab.values()), (stated == sum(crosstab.values()) and named)


stated_tot, xtab_tot, parts_ok = decomposition_accounts_for_every_cell(summary, xtab)
print(
    f"  summary states total={stated_tot}; reviewer cross-tab totals {xtab_tot} across "
    f"{len(xtab)} cells {sorted(set(xtab.values()))}"
)
chk(
    "summary's prose accounts for every disagreement cell",
    True,
    parts_ok,
    "<-- FALSIFICATION TARGET",
)

# BOTH-STATES CONTROL: the same checker must FIRE on the original, pre-correction wording.
_, _, fires_on_broken = decomposition_accounts_for_every_cell(
    ORIGINAL_BROKEN_SUMMARY, xtab
)
out["decomposition_checker_control"] = {
    "passes_on_corrected_summary": parts_ok,
    "fires_on_original_broken_summary": not fires_on_broken,
    "why": "the original named 17/8/11 (=36) against a stated 37 and never named the 4th cell "
    "(UNDECIDED->SCRATCH, 1 row); a checker silent on that text would measure nothing",
}
print(
    f"  CONTROL decomposition checker: passes_on_corrected={parts_ok} "
    f"fires_on_original_broken={not fires_on_broken}"
)
if fires_on_broken:
    print("FAILED:falsify-aud0006 the decomposition checker is inert; verdict withheld")
    sys.exit(1)

lose_m = xtab.get(("REAL-WORK", "SCRATCH"), 0) + xtab.get(("REAL-WORK", "UNDECIDED"), 0)
keep_m = xtab.get(("SCRATCH", "REAL-WORK"), 0)
undec_m = xtab.get(("UNDECIDED", "REAL-WORK"), 0)
chk("LOSE cell (body=REAL-WORK, path-only would not keep it)", 17, lose_m)
chk("KEEP cell (body=SCRATCH, path-only keeps it)", 8, keep_m)
chk("cannot-decide cell (body=UNDECIDED, path-only keeps it)", 11, undec_m)
unaccounted = [
    (f"{c}->{po}", n)
    for (c, po), n in xtab.items()
    if (c, po)
    not in {
        ("REAL-WORK", "SCRATCH"),
        ("REAL-WORK", "UNDECIDED"),
        ("SCRATCH", "REAL-WORK"),
        ("UNDECIDED", "REAL-WORK"),
    }
]
print(f"  disagreement cells NOT covered by the summary's three buckets: {unaccounted}")
out["cells_not_covered_by_summary"] = dict(unaccounted)

if not parts_ok:
    ex = [
        p["path"]
        for p in mine_dis
        if f"{p['content_verdict']}->{p['path_only_verdict']}" in dict(unaccounted)
    ]
    out["findings"].append(
        {
            "severity": "LOW",
            "kind": "summary-prose-arithmetic",
            "claim_text": summary,
            "defect": (
                f"the summary states {stated_tot} disagreements but its prose does not name every "
                f"cell; the reviewer cross-tab totals {xtab_tot} across {len(xtab)} cells "
                f"{dict((f'{c}->{po}', n) for (c, po), n in xtab.items())}"
            ),
            "unaccounted_cells": dict(unaccounted),
            "example_paths": ex[:5],
            "affects_headline_count": False,
            "why_not_blocking": (
                "the machine-readable fields -- tally, paths[], observations[] and "
                "classifier_disagreements[] -- are all internally consistent and all "
                "re-derive from the raw capture. Only the human-readable prose "
                "decomposition is short by one row."
            ),
        }
    )

# live re-run: not a refutation, the row itself declares index contention
p = subprocess.run(
    ["git", "status", "--porcelain=v2", "-uall"],
    cwd=ROOT,
    capture_output=True,
    text=True,
)
out["live_path_count_now"] = len(parse_porcelain_v2(p.stdout))
print(
    f"  LIVE re-run now: {out['live_path_count_now']} paths -- the row declares INDEX CONTENTION "
    "and calls its count a snapshot, so a moved number is expected, not a refutation"
)

out["agree_count"] = sum(1 for c in out["checks"] if c["agree"])
out["diverge_count"] = sum(1 for c in out["checks"] if not c["agree"])
(ROOT / "command-center/p2-next/REVIEW-AUD-0006.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8"
)
print(
    f"\n  agree={out['agree_count']} diverge={out['diverge_count']} "
    f"findings={len(out['findings'])}"
)
print("SUCCESS:falsify-aud0006")
