#!/usr/bin/env python3
"""Named probe 1: no-fit corpus + 100-query terminal-state audit.

Every labelled no-fit query must return NO-CAPABILITY-FITS. One hundred
seeded random queries (including adversarial non-strings) must all return a
terminal verdict; empty/null returns fail the probe. A labelled fit corpus
must still SELECT, so the detector is not 'always no-fit'.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = S.RECEIPT


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0396-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if doc.get("unit_id") != "IMP-0396":
        print("FAILED:IMP-0396-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() != "SUCCESS":
        print("FAILED:IMP-0396-probe1 state", doc.get("state"))
        return 1
    if S.SENTINEL not in text:
        print("FAILED:IMP-0396-probe1 sentinel absent")
        return 1

    n = S.load_nofit()
    caps = S.capabilities(n)
    nofit_q = S.nofit_queries(n)
    fit_q = S.fit_queries(n)

    corpus = n.nofit_corpus_all_nofit(caps, nofit_q)
    print(
        f"nofit_corpus n={corpus['n']} fail={corpus['n_fail']} "
        f"threshold={corpus['threshold']} pass={corpus['pass']}"
    )
    if not corpus["pass"]:
        print("FAILED:IMP-0396-probe1 no-fit corpus leaked a fit")
        print(json.dumps(corpus["failures"][:5], indent=2)[:2000])
        return 1

    for q in fit_q:
        result = n.route(q, caps)
        if not n.is_terminal(result) or result["verdict"] != n.VERDICT_SELECTED:
            print(f"FAILED:IMP-0396-probe1 fit query not SELECTED {q!r} {result.get('verdict')}")
            return 1
    print(f"fit_corpus n={len(fit_q)} all_selected=True")

    audit = n.terminal_audit(caps, extra=nofit_q + fit_q)
    print(
        f"terminal_audit n={audit['n']} terminal={audit['terminal']} "
        f"non_terminal={audit['non_terminal']} empty_or_null={audit['empty_or_null']} "
        f"verdicts={audit['verdicts']} pass={audit['pass']}"
    )
    if not audit["pass"]:
        print("FAILED:IMP-0396-probe1 non-terminal return in 100-query audit")
        print(json.dumps(audit["failures"][:8], indent=2)[:2000])
        return 1
    if audit["terminal"] != 100 or audit["empty_or_null"] != 0:
        print("FAILED:IMP-0396-probe1 audit counts")
        return 1

    recorded = doc.get("terminal_state_audit") or {}
    if int(recorded.get("n") or 0) != 100 or int(recorded.get("terminal") or 0) != 100:
        print("FAILED:IMP-0396-probe1 receipt audit does not claim 100/100")
        return 1
    if int(recorded.get("empty_or_null", -1)) != 0:
        print("FAILED:IMP-0396-probe1 receipt empty_or_null")
        return 1
    if int(recorded.get("seed") or 0) != audit["seed"]:
        print("FAILED:IMP-0396-probe1 receipt seed drift")
        return 1
    if recorded.get("verdicts") != audit["verdicts"]:
        print("FAILED:IMP-0396-probe1 receipt verdict tally drift")
        print("recorded", recorded.get("verdicts"))
        print("live", audit["verdicts"])
        return 1

    hunt = n.silence_hunt(caps)
    print(
        f"silence_hunt attempts={hunt['attempts']} hits={len(hunt['non_terminal_hits'])} "
        f"pass={hunt['pass']}"
    )
    if not hunt["pass"]:
        print("FAILED:IMP-0396-probe1 silence hunt found a non-terminal return")
        return 1

    print("SUCCESS:IMP-0396-probe1 no-fit corpus and terminal-state audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
