#!/usr/bin/env python3
"""Refuse a prose tool-count that EXCEEDS the surface it is attributed to.

WHY THIS EXISTS.  An independent audit of round 2 found a sentence claiming ``search-hub``
had ``113 non-exa tools``.  Its real surface is **68**, so 113 cannot be a subset of it --
and 113 is exactly ``424 - 311``, a *cloud-hub* number that migrated into a search-hub
sentence one paragraph away.  Every gate in this directory passed, because nothing computes
from that number: it lives in prose, and prose is the one surface with no producer.

The invariant that catches it is not "is this number right" (undecidable) but the weaker,
mechanical one:

    A count attributed to server X can never exceed X's committed ``tool_count``.

Subset claims -- "23 advertised tools", "4 tool names", "157 tools over 7 backends" -- are
all strictly less than their server's total and pass untouched.  Only an *over*-count fires,
and an over-count is provably wrong under every reading of the sentence.  That asymmetry is
the whole design: it buys a real check cheaply.  SCOPE of the false-positive claim, since
this file exists to punish unscoped claims: zero false positives were observed on the 11
documents of ``docs/mcp-audit`` at the round-3 commit, after the two rules below were
narrowed.  That is a measurement on one corpus, not a general property.

ATTRIBUTION.  A count is attributed to the NEAREST PRECEDING server mention inside its
paragraph -- because the defect it exists to catch spans lines (``search-hub`` is named two
lines above ``113``), so a line-scoped reader would have been silent on the very sentence
that produced it.  A line-scoped version was written first and measured: it found 0 of 1.
That is a control that cannot distinguish the two hypotheses, and it is why this reads
paragraphs.

TWO THINGS ARE NOT LINTED, both for the same reason: they are not claims.

  * FENCED BLOCKS.  Text inside ``` fences is captured command output.  It is evidence, a
    program produced it, and editing it to satisfy a linter would be fabrication.
  * INLINE CODE SPANS.  A figure written as `999 tools` is a literal string being quoted --
    typically this lane's own documentation describing its own fixtures.  The same figure
    asserted in plain prose still fires, and the self-test holds exactly that pair so the
    rule cannot quietly widen into a blanket hole.

Both counts are REPORTED on every run rather than dropped, so the size of the blind spot is
visible instead of implied.

WHAT THIS IS NOT.  It cannot tell a right number from a wrong one that happens to fit, and
it says so in its own output rather than implying whole-corpus correctness.

Run::

    python claim_lint.py                 # lint the shipped docs
    python claim_lint.py --self-test     # both-states controls, incl. the real defect text
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
DOCS = REPO / "docs" / "mcp-audit"
MATRIX = "capability-matrix-r2.json"
CROSS = "disposition.json"

# A count, then at most three plain words, then "tool"/"tools".  The intervening words may
# not contain a period, so a match cannot straddle a sentence boundary.
COUNT_RE = re.compile(
    r"(\d[\d,]*)\s+((?:[A-Za-z][\w-]*\s+){0,3})tools?\b", re.IGNORECASE
)

# An inline code span is a literal string being QUOTED, not a claim being made -- `999 tools`
# in a sentence about a test fixture is a mention, not an assertion about a server.  This
# lane has shipped use-vs-mention defects repeatedly, twice inside its own measuring tools,
# so the boundary is drawn structurally instead of case by case.
#
# Only the COUNT match is suppressed, never the span: server names in this corpus are almost
# always written as `search-hub`, and blanking spans wholesale would delete the attribution
# anchors along with the mentions.  `context7` is the reason a cruder "blank any span holding
# a digit" rule was rejected -- it would erase a roster server's name.
CODESPAN_RE = re.compile(r"`[^`\n]*`")

# USE-vs-MENTION exemptions, each with a written reason.  A key is (doc, count, server) --
# deliberately narrow, so a DIFFERENT over-count in the same document still fires.
#
# These are not "the linter is wrong".  They are documents that must QUOTE a refuted figure
# in order to record that it was refuted: the contract this lane works under says to fix the
# sentence and record the refutation, never to delete the wrong number so the problem
# disappears.  Rephrasing to slip past the matcher would leave the same text on the page
# while the gate reported clean, so the exemption is declared here and PRINTED on every run
# instead.  An exemption nobody sees is how a gate rots.
ALLOW: dict[tuple[str, int, str], str] = {
    ("LANE-MCPRESEARCH-BUILD-R2.md", 113, "search-hub"): (
        "the round-2 report's own inline REFUTED note, which must restate the wrong figure "
        "it is retracting"
    ),
    ("LANE-MCPRESEARCH-BUILD-R3.md", 113, "search-hub"): (
        "the round-3 report quotes the refuted figure as the defect under repair"
    ),
    ("LANE-MCPRESEARCH-BUILD-R3B.md", 113, "search-hub"): (
        "round 3B's finding table restates D1 to say which defect round 3 closed. Declared "
        "rather than rephrased: this gate fired on it unprompted, and quietly rewording the "
        "row to slip past a guard that just worked correctly is the failure the exemption "
        "mechanism exists to make visible"
    ),
}


def roster(base: pathlib.Path) -> tuple[dict[str, int], list[str]]:
    """{server: tool_count} for servers with a sampled surface, plus the unsampled names.

    Cross-checked against ``disposition.json``.  Two artifacts that disagree about the size
    of the fleet's surface would make every verdict below meaningless, so a disagreement
    raises rather than picking one -- the roster is the denominator of this whole file.
    """
    mat = json.loads((base / MATRIX).read_text(encoding="utf-8"))
    disp = json.loads((base / CROSS).read_text(encoding="utf-8"))
    counts = {r["name"]: r.get("tool_count") for r in mat["rows"]}
    other = {r["name"]: r.get("tool_count") for r in disp["rows"]}
    if counts != other:
        diff = {k: (v, other.get(k)) for k, v in counts.items() if other.get(k) != v}
        raise SystemExit(
            f"FAILED:claim-lint roster disagreement {MATRIX} vs {CROSS}: {diff}"
        )
    sampled = {k: v for k, v in counts.items() if isinstance(v, int)}
    unsampled = sorted(k for k, v in counts.items() if not isinstance(v, int))
    if not sampled:
        raise SystemExit(
            "FAILED:claim-lint empty roster -- refusing to certify prose against nothing"
        )
    return sampled, unsampled


def name_re(names: list[str]) -> re.Pattern[str]:
    """Longest-first alternation so ``playwright-cdp`` never matches as ``playwright``."""
    alt = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return re.compile(rf"(?<![\w-])({alt})(?![\w-])")


def paragraphs(text: str) -> list[tuple[int, str]]:
    """(line_no, paragraph) for prose only -- fenced blocks are dropped, not linted."""
    out: list[tuple[int, str]] = []
    buf: list[str] = []
    start = 1
    fenced = False
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            line = ""
        if fenced:
            line = ""
        if line.strip():
            if not buf:
                start = i
            buf.append(line)
        elif buf:
            out.append((start, "\n".join(buf)))
            buf = []
    if buf:
        out.append((start, "\n".join(buf)))
    return out


def scan(text: str, counts: dict[str, int], doc: str = "") -> dict[str, Any]:
    """Attribute every tool-count in ``text`` and flag those exceeding their server."""
    rx = name_re(list(counts))
    claims: list[dict[str, Any]] = []
    unattributed = 0
    quoted = 0
    for lineno, para in paragraphs(text):
        mentions = [(m.start(), m.group(1)) for m in rx.finditer(para)]
        if not mentions:
            unattributed += sum(1 for _ in COUNT_RE.finditer(para))
            continue
        spans = [(m.start(), m.end()) for m in CODESPAN_RE.finditer(para)]
        for m in COUNT_RE.finditer(para):
            if any(a <= m.start() and m.end() <= b for a, b in spans):
                quoted += 1
                continue
            n = int(m.group(1).replace(",", ""))
            before = [s for p, s in mentions if p < m.start()]
            # A count with NO server before it has no textual attribution, so it is left
            # unattributed rather than bound to the next name downstream.  Measured: the
            # first version attributed to the first mention in the paragraph either way,
            # and that fallback produced this file's only false positive -- "707 tools"
            # (the FLEET total) charged to cloud-hub because cloud-hub happened to be
            # named two sentences later.  Narrowing the rule removed it structurally;
            # exempting it would have left the same trap armed for every future summary.
            if not before:
                unattributed += 1
                continue
            server = before[-1]
            limit = counts[server]
            fits = sorted({s for _, s in mentions if counts[s] >= n and s != server})
            claims.append(
                {
                    "doc": doc,
                    # the line of the MATCH, not of the paragraph: a bullet list is one
                    # paragraph and can run 20 lines, so reporting its head sends the
                    # reader to the wrong sentence.
                    "line": lineno + para.count("\n", 0, m.start()),
                    "text": m.group(0).strip(),
                    "count": n,
                    "server": server,
                    "limit": limit,
                    "over": n > limit,
                    "would_fit": fits if n > limit else [],
                    "allowed": (doc, n, server) in ALLOW,
                }
            )
    return {"claims": claims, "unattributed": unattributed, "quoted": quoted}


def lint(base: pathlib.Path, docs: pathlib.Path) -> dict[str, Any]:
    counts, unsampled = roster(base)
    files = sorted(docs.glob("*.md"))
    if not files:
        raise SystemExit(f"FAILED:claim-lint no documents under {docs} -- fail closed")
    claims: list[dict[str, Any]] = []
    unattributed = 0
    quoted = 0
    for f in files:
        res = scan(f.read_text(encoding="utf-8"), counts, f.name)
        claims.extend(res["claims"])
        unattributed += res["unattributed"]
        quoted += res["quoted"]
    # C1 -- DETECTOR CONTROL.  A reader that extracts nothing reports a clean corpus and
    # proves nothing.  Zero claims over 10 audit documents is a broken matcher, not a clean
    # corpus, so it fails closed.
    if not claims:
        raise SystemExit(
            f"FAILED:claim-lint extracted 0 attributed counts from {len(files)} documents "
            "-- the matcher is broken, not the corpus clean"
        )
    violations = [c for c in claims if c["over"] and not c["allowed"]]
    exempt = [c for c in claims if c["over"] and c["allowed"]]
    # C2 -- a declared exemption that no longer matches anything is stale scaffolding, and
    # stale scaffolding in a gate is how the next real over-count gets waved through.
    stale = sorted(set(ALLOW) - {(c["doc"], c["count"], c["server"]) for c in exempt})
    return {
        "files": len(files),
        "claims": claims,
        "violations": violations,
        "exempt": exempt,
        "stale_allow": stale,
        "unattributed": unattributed,
        "quoted": quoted,
        "unsampled": unsampled,
        "servers": len(counts),
    }


# ---------------------------------------------------------------- both-states self-test
# The real defect text, verbatim from LANE-MCPRESEARCH-BUILD-R2.md before this round, and
# the corrected text.  A fixture invented for the test would only prove the test runs.
BROKEN = """- **`dead_surface_pct` is still null for every non-`cloud-hub` row**, `search-hub` included.
  Its four backends are now all *measured*, but no tool->backend map exists for it, so its
  113 non-exa tools cannot be attributed by bytes. Null means **not attributed**, never zero.
"""
FIXED = """- **`dead_surface_pct` is still null for every non-`cloud-hub` row**, `search-hub` included.
  Its four backends are now all *measured*, but no tool->backend map exists for it, so its
  54 non-exa tools (of 68) cannot be attributed by bytes. Null means **not attributed**.
"""
FENCED = """Prose says search-hub is fine.

```
search-hub  999 tools
```
"""
SUBSET = "`cloud-hub` refuses to dispatch 23 advertised tools.\n"
LINE_SCOPED_MISS = "  113 non-exa tools cannot be attributed by bytes.\n"
# The corpus's one false positive under the first (fallback) attribution rule: a fleet total
# that PRECEDES every server mention in its paragraph.
FLEET_FIRST = (
    "cost is measured for 707 tools in both channels, and `cloud-hub` = 424 held.\n"
)
# A code span is a MENTION.  The pair below is what stops that rule being a blanket hole:
# identical figure, identical server, one quoted and one asserted.
QUOTED_MENTION = "The `search-hub` fixture in the self-test reads `999 tools`.\n"
PLAIN_CLAIM = "The `search-hub` fixture in the self-test reads 999 tools.\n"


def self_test(base: pathlib.Path) -> int:
    counts, _ = roster(base)
    cases: list[tuple[str, bool, bool]] = []

    broken = scan(BROKEN, counts, "fx")
    over = [c for c in broken["claims"] if c["over"]]
    cases.append(("the REAL defect text fires", bool(over), True))
    cases.append(
        (
            "  ...attributed to search-hub, not cloud-hub",
            bool(over) and over[0]["server"] == "search-hub",
            True,
        )
    )
    cases.append(
        (
            "  ...and names cloud-hub as where 113 would fit",
            bool(over) and "cloud-hub" in over[0]["would_fit"],
            True,
        )
    )
    cases.append(
        (
            "the CORRECTED text is silent",
            any(c["over"] for c in scan(FIXED, counts, "fx")["claims"]),
            False,
        )
    )
    cases.append(
        (
            "a subset claim (23 of cloud-hub's 424) is silent",
            any(c["over"] for c in scan(SUBSET, counts, "fx")["claims"]),
            False,
        )
    )
    fen = scan(FENCED, counts, "fx")
    cases.append(("a fenced receipt is not linted", bool(fen["claims"]), False))
    # The control that earned this file its paragraph scope: the defect's own line, alone,
    # names no server.  A line-scoped reader sees nothing -- and would have reported clean.
    cases.append(
        (
            "the defect LINE alone attributes to nobody (why this reads paragraphs)",
            bool(scan(LINE_SCOPED_MISS, counts, "fx")["claims"]),
            False,
        )
    )
    # The measured false positive, and the rule that removed it.  Kept as a fixture so a
    # future "improvement" that reinstates the fallback goes red here instead of in review.
    fleet = scan(FLEET_FIRST, counts, "fx")
    cases.append(
        (
            "a fleet total preceding every server name is NOT attributed",
            any(c["count"] == 707 for c in fleet["claims"]),
            False,
        )
    )
    cases.append(
        (
            "  ...and is counted as unattributed, not dropped",
            fleet["unattributed"] >= 1,
            True,
        )
    )
    # The code-span rule, both states.  Same figure, same server, same sentence -- the ONLY
    # difference is the backticks, so a pass here cannot come from anything else.
    cases.append(
        (
            "a count QUOTED in a code span is a mention, not a claim",
            any(c["over"] for c in scan(QUOTED_MENTION, counts, "fx")["claims"]),
            False,
        )
    )
    cases.append(
        (
            "  ...but the SAME figure asserted in plain prose still fires",
            any(c["over"] for c in scan(PLAIN_CLAIM, counts, "fx")["claims"]),
            True,
        )
    )
    cases.append(
        (
            "  ...and the quoted one is counted, not silently dropped",
            scan(QUOTED_MENTION, counts, "fx")["quoted"] == 1,
            True,
        )
    )
    # ALLOW must suppress the exact triple and nothing wider.
    hit = scan(BROKEN, counts, "LANE-MCPRESEARCH-BUILD-R3.md")["claims"]
    cases.append(
        (
            "a declared exemption marks its own claim allowed",
            any(c["allowed"] for c in hit),
            True,
        )
    )
    other = scan(BROKEN, counts, "SOME-OTHER-DOC.md")["claims"]
    cases.append(
        (
            "  ...and does NOT cover the same figure in another document",
            any(c["allowed"] for c in other),
            False,
        )
    )
    # An empty roster must fail closed rather than certify prose against nothing.
    try:
        scan(BROKEN, {}, "fx")
        empty_ok = False
    except (ValueError, KeyError, IndexError, re.error):
        empty_ok = True
    cases.append(("an empty roster cannot silently certify", empty_ok, True))

    bad = [n for n, got, want in cases if got != want]
    for n, got, want in cases:
        print(f"  {'ok ' if got == want else 'BAD'} {n:62} fired={got} want={want}")
    if bad:
        print(f"FAILED:claim-lint self-test {bad}")
        return 1
    print(f"SUCCESS:claim-lint self-test {len(cases)}/{len(cases)} controls behaved")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=str(HERE))
    ap.add_argument("--docs", default=str(DOCS))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    base = pathlib.Path(args.base)

    if args.self_test:
        return self_test(base)

    res = lint(base, pathlib.Path(args.docs))
    print(
        f"  scanned {res['files']} documents against {res['servers']} sampled servers; "
        f"{len(res['claims'])} attributed tool-counts, {res['quoted']} quoted in code spans "
        f"(mentions, not claims), {res['unattributed']} in paragraphs "
        f"naming no server first (not checkable), {len(res['unsampled'])} servers unsampled "
        f"(no stdio child -- their prose counts cannot be checked at all)"
    )
    for c in res["exempt"]:
        print(
            f'  EXEMPT {c["doc"]}:{c["line"]} "{c["text"]}" -> {c["server"]} '
            f"(surface {c['limit']}): {ALLOW[(c['doc'], c['count'], c['server'])]}"
        )
    for c in res["violations"]:
        # would_fit distinguishes the two failure shapes: a number that fits ANOTHER server
        # named nearby is a cross-row transposition (the D1 shape); a number that fits none
        # of them is a different SCOPE entirely -- a fleet or aggregate total (the O1 shape).
        hint = (
            f"; fits {c['would_fit']} -- looks TRANSPOSED from that row"
            if c["would_fit"]
            else "; fits no server named here -- looks like an aggregate/fleet number"
        )
        print(
            f'  OVER {c["doc"]}:{c["line"]} "{c["text"]}" attributed to {c["server"]} '
            f"(surface {c['limit']}){hint}"
        )
    for key in res["stale_allow"]:
        print(f"  STALE-ALLOW {key} no longer matches any claim -- delete it")
    if res["violations"] or res["stale_allow"]:
        print(
            f"FAILED:claim-lint {len(res['violations'])} count(s) exceed their server's "
            f"surface, {len(res['stale_allow'])} stale exemption(s)"
        )
        return 1
    print(
        f"SUCCESS:claim-lint {len(res['claims'])} attributed counts over {res['files']} docs, "
        f"0 exceed their server, {len(res['exempt'])} declared use-vs-mention exemption(s) "
        "(a count that FITS is not thereby verified -- this bounds, it does not certify)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
