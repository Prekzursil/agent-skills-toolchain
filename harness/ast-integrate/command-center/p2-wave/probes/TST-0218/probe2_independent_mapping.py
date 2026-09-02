#!/usr/bin/env python3
"""Probe 2: independent confusable mapping over the same 100 names.

Does not import fold_name, levenshtein, or the homoglyph table from
marketplace.name_linter. Skeleton:

  * NFKD + strip combining marks (linter uses NFKC + a codepoint table)
  * map lookalikes via unicodedata.name() + a name-keyed visual table
  * delete separators instead of collapsing them to '-'
  * full-matrix Levenshtein (linter uses two-row WF)

Then compare flag decisions to the production linter. Identity-only mutant
(raw string equality) must miss every confusable pair, proving the fold is live.
"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))

from corpus import CONFUSABLE, DISTINCT_CANDIDATES, INSTALLED, assert_corpus  # noqa: E402
from marketplace.name_linter import lint_candidate  # noqa: E402  # SUT only; not fold_name

# Visual Latin targets keyed by the Unicode *name* remainder after "LETTER ".
# Independent of the linter's codepoint table.
_LETTER_NAME_LATIN = {
    "A": "a",
    "IE": "e",
    "O": "o",
    "ER": "p",
    "ES": "c",
    "HA": "x",
    "U": "y",
    "VE": "b",
    "I": "i",
    "BYELORUSSIAN-UKRAINIAN I": "i",
    "OMICRON": "o",
    "ALPHA": "a",
    "RHO": "p",
    "CHI": "x",
    "IOTA": "i",
}

_EDIT_MAX = 1
_EDIT_MIN_LEN = 4


def independent_fold(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    out: list[str] = []
    for ch in text:
        if unicodedata.combining(ch):
            continue
        uname = unicodedata.name(ch, "")
        if uname == "DIGIT ZERO":
            out.append("o")
            continue
        if ch in "-_.":
            continue
        mapped = _latin_from_letter_name(uname)
        if mapped is not None:
            out.append(mapped)
            continue
        out.append(ch.casefold())
    return "".join(out)


def _latin_from_letter_name(uname: str) -> str | None:
    if "LETTER" not in uname:
        return None
    rest = uname.split("LETTER ", 1)[1].strip()
    if rest in _LETTER_NAME_LATIN:
        return _LETTER_NAME_LATIN[rest]
    if len(rest) == 1 and rest.isalpha():
        return rest.lower()
    return None


def independent_levenshtein(a: str, b: str) -> int:
    """Full (n+1)*(m+1) matrix; mechanically different from the two-row linter."""
    n, m = len(a), len(b)
    mtx = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        mtx[i][0] = i
    for j in range(m + 1):
        mtx[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            mtx[i][j] = min(
                mtx[i - 1][j] + 1,
                mtx[i][j - 1] + 1,
                mtx[i - 1][j - 1] + cost,
            )
    return mtx[n][m]


def independent_flags(candidate: str, installed: list[str]) -> list[str]:
    fc = independent_fold(candidate)
    hits: list[str] = []
    for name in installed:
        fi = independent_fold(name)
        if fc == fi:
            hits.append(name)
            continue
        d = independent_levenshtein(fc, fi)
        if d <= _EDIT_MAX and min(len(fc), len(fi)) >= _EDIT_MIN_LEN:
            hits.append(name)
    return hits


def identity_flags(candidate: str, installed: list[str]) -> list[str]:
    return [n for n in installed if n == candidate]


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:TST-0218-probe2 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:4000])
    return 1


def main() -> int:
    assert_corpus()
    installed = list(INSTALLED)
    disagreements: list[dict] = []
    identity_hits_on_confusable = 0
    independent_tp = 0
    independent_fp = 0

    for target, candidate, kind in CONFUSABLE:
        indie = independent_flags(candidate, installed)
        sut = [f.confused_with for f in lint_candidate(candidate, installed)]
        if target not in indie:
            disagreements.append(
                {
                    "where": "independent-miss-confusable",
                    "target": target,
                    "candidate": candidate,
                    "kind": kind,
                    "independent": indie,
                    "linter": sut,
                }
            )
        else:
            independent_tp += 1
        if set(indie) != set(sut):
            disagreements.append(
                {
                    "where": "linter-vs-independent",
                    "target": target,
                    "candidate": candidate,
                    "kind": kind,
                    "independent": indie,
                    "linter": sut,
                }
            )
        if identity_flags(candidate, installed):
            identity_hits_on_confusable += 1

    for candidate in DISTINCT_CANDIDATES:
        indie = independent_flags(candidate, installed)
        sut = [f.confused_with for f in lint_candidate(candidate, installed)]
        if indie:
            independent_fp += 1
            disagreements.append(
                {
                    "where": "independent-false-positive",
                    "candidate": candidate,
                    "independent": indie,
                    "linter": sut,
                }
            )
        if set(indie) != set(sut):
            disagreements.append(
                {
                    "where": "linter-vs-independent-distinct",
                    "candidate": candidate,
                    "independent": indie,
                    "linter": sut,
                }
            )

    payload = {
        "probe": "probe2-independent-mapping",
        "unit_id": "TST-0218",
        "reviewer_id": "TST-0218-probe2-independent-confusable-mapping",
        "independent_tp": independent_tp,
        "independent_fp": independent_fp,
        "identity_mutant_hits_on_confusable": identity_hits_on_confusable,
        "disagreement_n": len(disagreements),
        "disagreements": disagreements[:12],
        "fold": "NFKD+strip-combining+unicodedata.name+delete-separators",
        "distance": "full-matrix-levenshtein",
        "pass": True,
    }

    if identity_hits_on_confusable != 0:
        payload["pass"] = False
        return fail(
            "identity mutant must miss every confusable pair "
            f"(hits={identity_hits_on_confusable})",
            payload,
        )
    if independent_tp != 50:
        payload["pass"] = False
        return fail("independent mapping missed a labeled confusable pair", payload)
    if independent_fp != 0:
        payload["pass"] = False
        return fail("independent mapping flagged a distinct pair", payload)
    if disagreements:
        payload["pass"] = False
        return fail("linter and independent mapping disagree", payload)

    print(json.dumps(payload, sort_keys=True))
    print(
        f"independent_tp={independent_tp} independent_fp={independent_fp} "
        f"identity_mutant_hits={identity_hits_on_confusable} disagreements=0"
    )
    print("SUCCESS:TST-0218-probe2 independent mapping agrees; identity mutant silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
