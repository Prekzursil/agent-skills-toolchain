"""Catch an AGGREGATE published under a wider scope than it measures.

WHY THIS EXISTS
---------------
An independent audit CONFIRMED two overclaims against round 2.  Round 3 closed the first
(a per-row share quoted without its denominator) with ``cost_rank``'s C5, and the second
survived it: the block one level up was still named ``fleet`` while holding sums over the
16 sampled rows only.  ``707 tools`` / ``11,645 B`` / ``603,233 B`` were then copied into
prose as fleet totals -- including by round 3's own report, which calls 707 "the fleet
total" three sections after fixing the share.  C5 was green through all of it, because a
control on the share cannot see the scope of the aggregate that feeds it.

``claim_lint`` cannot catch this either, and that is by design rather than by oversight:
it bounds a count against the server it is attributed to, and an aggregate is attributed
to no server.  Its own docs record ``707`` as the corpus's one false positive under the
attribution rule it then removed.  So the aggregate class needed its own reader.

WHAT IT ENFORCES
----------------
    A paragraph quoting a sampled-only aggregate must also carry its scope.

The figures are READ FROM ``cost-rank.json`` at run time, never hardcoded, so the lint
tracks the producer instead of drifting from it.  Fenced blocks are excluded through
``claim_lint.paragraphs``: a figure inside a ``` fence is captured output, and editing
captured output to satisfy a linter is fabrication.

This is a BOUND, not a certificate.  A paragraph that carries a scope token is not thereby
correct -- only the unscoped direction is decidable this way.

    python scope_lint.py [--base DIR] [--docs DIR]
    python scope_lint.py --self-test
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from claim_lint import paragraphs  # noqa: E402  -- sys.path set immediately above

REPO = HERE.parent.parent
DOCS = REPO / "docs" / "mcp-audit"

# Structural phrases, not bare digits: "16" and "23" occur inside unrelated byte counts and
# would let a paragraph pass for the wrong reason (the same trap C5 documents).
SCOPE_RE = re.compile(
    r"16\s+SAMPLED|16\s*(?:of|/)\s*23|of\s+23\s+rows|sampled|16\s+ranked|16\s+rows|"
    r"servers_ranked|sampled_aggregate",
    re.IGNORECASE,
)

# Declared use-vs-mention exemptions, keyed narrowly to (document, figure) and PRINTED on
# every run.  Rounds must be able to QUOTE the refuted framing in order to record that it
# was refuted; rephrasing to slip past the matcher would leave the same text on the page
# while the gate reported clean.  A stale exemption fails the run.
ALLOW: dict[tuple[str, str], str] = {
    # No entry for LANE-MCPRESEARCH-BUILD-R3.md: its 707 paragraph was CORRECTED to carry
    # its scope rather than exempted.  An exemption is the last resort, not the first --
    # it leaves the text on the page while the gate reports clean.
    (
        "LANE-MCPRESEARCH-BUILD-R3B.md",
        "707",
    ): "round 3B must restate the refuted 'fleet total' wording to record that it was refuted",
}


def figures(base: pathlib.Path) -> dict[str, int]:
    """The sampled-only aggregate values, read from the producer's own artifact."""
    cost = json.loads((base / "cost-rank.json").read_text(encoding="utf-8"))
    agg = cost.get("sampled_aggregate")
    if not agg:
        raise SystemExit(
            "FAILED:scope-lint cost-rank.json has no `sampled_aggregate` block -- either "
            "the producer regressed to the `fleet` label or the schema moved; refusing to "
            "lint against figures I cannot locate"
        )
    return {
        "tools": agg["tools_sampled"],
        "resident": agg["resident_bytes_sampled"],
        "contingent": agg["contingent_bytes_sampled"],
    }


def patterns(vals: dict[str, int]) -> dict[str, re.Pattern[str]]:
    """Bounded on both sides by digit/comma/period.

    A bare ``"707" in para`` matches ``4,707`` -- scholarly-access's schema bytes -- and
    invents sites that do not exist.  Measured: the unbounded first version reported a
    DISPOSITION-TABLE.md site that is not there.  Control C4 holds that line.
    """
    out: dict[str, re.Pattern[str]] = {}
    for v in vals.values():
        for text in (f"{v:,}", str(v)):
            out[text] = re.compile(r"(?<![\d,.])" + re.escape(text) + r"(?![\d,.])")
    return out


def scan(docs: pathlib.Path, vals: dict[str, int]) -> dict[str, Any]:
    pats = patterns(vals)
    hits: list[dict[str, Any]] = []
    used: set[tuple[str, str]] = set()
    seen = 0
    for doc in sorted(docs.glob("*.md")):
        text = doc.read_text(encoding="utf-8")
        for start, para in paragraphs(text):
            for fig, pat in pats.items():
                if not pat.search(para):
                    continue
                seen += 1
                if SCOPE_RE.search(para):
                    continue
                key = (doc.name, fig.replace(",", ""))
                alt = (doc.name, fig)
                if key in ALLOW or alt in ALLOW:
                    used.add(key if key in ALLOW else alt)
                    continue
                hits.append({"doc": doc.name, "line": start, "figure": fig})
    return {"seen": seen, "unscoped": hits, "exemptions_used": sorted(used)}


def lint(base: pathlib.Path, docs: pathlib.Path) -> dict[str, Any]:
    vals = figures(base)
    res = scan(docs, vals)
    res["figures"] = vals
    return res


def _report(res: dict[str, Any]) -> int:
    for h in res["unscoped"]:
        print(f"  UNSCOPED  {h['doc']}:{h['line']}  quotes {h['figure']} with no scope")
    for d, f in res["exemptions_used"]:
        print(f"  exempt    {d} [{f}]  {ALLOW[(d, f)]}")
    # Fail closed: zero extraction over a corpus that demonstrably contains these figures is
    # a broken matcher, not a clean corpus.
    if res["seen"] == 0:
        print(
            "FAILED:scope-lint 0 occurrences found -- the matcher is broken, not the corpus"
        )
        return 1
    stale = sorted(set(ALLOW) - set(res["exemptions_used"]))
    if stale:
        print(f"FAILED:scope-lint stale exemption(s) {stale} matched nothing")
        return 1
    if res["unscoped"]:
        print(
            f"FAILED:scope-lint {len(res['unscoped'])} paragraph(s) quote a SAMPLED-ONLY "
            "aggregate as if it were a fleet total"
        )
        return 1
    print(
        f"SUCCESS:scope-lint {res['seen']} aggregate quotation(s) over the lane's docs, "
        f"0 unscoped, {len(res['exemptions_used'])} declared use-vs-mention exemption(s) "
        "(a scoped paragraph is not thereby verified -- this bounds, it does not certify)"
    )
    return 0


def self_test(base: pathlib.Path) -> int:
    """Every control must FIRE on its broken state and stay SILENT on the good one."""
    print("== scope_lint self-test (each control: fires broken, silent good) ==")
    vals = figures(base)
    pats = patterns(vals)
    cases: list[tuple[str, bool, bool]] = []

    # C1 -- the VERBATIM shipped defect, not a fixture invented to be caught.
    defect = "real-call verdict (was 2), per-server context cost is measured for 707 tools in both"
    cases.append(
        (
            "C1 the verbatim MCP-FLEET-AUDIT.md sentence is unscoped",
            not SCOPE_RE.search(defect),
            True,
        )
    )
    fixed = "context cost is measured for the 707 tools of the 16 SAMPLED rows (of 23)"
    cases.append(
        ("C2 the corrected sentence is scoped", bool(SCOPE_RE.search(fixed)), True)
    )

    # C3/C4 -- the matcher earned this one.  `4,707` is scholarly-access's schema bytes.
    row = "| scholarly-access | 8 | 144 | 4,707 | 0.8% | 0.9 |"
    cases.append(
        ("C3 '4,707' does NOT count as '707'", bool(pats["707"].search(row)), False)
    )
    cases.append(
        ("C4 a bare '707' still counts", bool(pats["707"].search(defect)), True)
    )

    # C5 -- fenced receipts are captured output, never claims.
    fenced = "```\nfleet tools 707 | name bytes 11,645\n```\n"
    cases.append(
        (
            "C5 a fenced receipt is not linted",
            any("707" in p for _, p in paragraphs(fenced)),
            False,
        )
    )

    # C6 -- fail closed on zero extraction (an empty corpus must not certify).
    empty = self_test.__dict__.setdefault("_tmp", base / "_scope_lint_empty")
    empty.mkdir(exist_ok=True)
    try:
        res = scan(empty, vals)
        cases.append(("C6 an empty corpus extracts nothing", res["seen"] == 0, True))
        cases.append(
            (
                "C6 ...and _report fails closed on it",
                _report({**res, "figures": vals}) == 1,
                True,
            )
        )
    finally:
        empty.rmdir()

    # C7 -- the producer regressing to the `fleet` label must break the lint, not be ignored.
    fired = False
    try:
        figures(base.parent)  # a directory with no cost-rank.json
    except (SystemExit, FileNotFoundError, OSError):
        fired = True
    cases.append(("C7 a missing/renamed aggregate block fails closed", fired, True))

    # C8 -- the shipped corpus is clean under the shipped figures.
    cases.append(
        (
            "C8 the shipped corpus has no unscoped site",
            bool(lint(base, DOCS)["unscoped"]),
            False,
        )
    )

    bad = [n for n, got, want in cases if got != want]
    for n, got, want in cases:
        print(f"  {'ok ' if got == want else 'BAD'} {n:58} fired={got} want={want}")
    if bad:
        print(f"FAILED:scope-lint self-test {bad}")
        return 1
    print(f"SUCCESS:scope-lint self-test {len(cases)}/{len(cases)} controls behaved")
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
    return _report(lint(base, pathlib.Path(args.docs)))


if __name__ == "__main__":
    raise SystemExit(main())
