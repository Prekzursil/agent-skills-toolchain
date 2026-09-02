#!/usr/bin/env python3
"""Probe 1: both-states + corpus false-positive rate as a number.

Genuinely-obvious named fixture must be SILENT. Sycophantic named fixture
must FIRE and contract blind re-evaluation. Corpus FP rate is reported as
fires/obvious, not as an adjective.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402
import overclaim as O  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0059-unanimity-and-the-instant-unanimity-suspicion-trigger.md"
)


def rate(rows: list[dict], want_fire: bool) -> tuple[int, int, float]:
    n = len(rows)
    hits = sum(1 for t in rows if bool(D.evaluate(t).get("fire")) is want_fire)
    return hits, n, (hits / n if n else 0.0)


def main() -> int:
    F.dump_named()
    good = F.load_named(F.NAMED_OBVIOUS)
    bad = F.load_named(F.NAMED_SYCOPHANTIC)
    # Detector must not see the label.
    g = D.evaluate(good["transcript"])
    b = D.evaluate(bad["transcript"])
    print("named_obvious " + D.verbatim_line(g))
    print("named_sycophantic " + D.verbatim_line(b))
    if g.get("fire"):
        print("FAILED:CNL-0059-probe1 obvious fixture triggered re-evaluation")
        return 1
    if not b.get("fire"):
        print("FAILED:CNL-0059-probe1 sycophantic fixture was silent")
        return 1
    if b.get("remediation") != "blind_re_evaluation":
        print("FAILED:CNL-0059-probe1 sycophantic remediation is not blind_re_evaluation")
        return 1

    by = F.transcripts_by_label()
    obvious = by["obvious"]
    syc = by["sycophantic"]
    fp_hits, fp_n, fp = (
        sum(1 for t in obvious if D.evaluate(t).get("fire")),
        len(obvious),
        0.0,
    )
    fp = fp_hits / fp_n if fp_n else 0.0
    fn_hits = sum(1 for t in syc if not D.evaluate(t).get("fire"))
    fn_n = len(syc)
    fn = fn_hits / fn_n if fn_n else 0.0
    print(f"obvious_n={fp_n} obvious_fires={fp_hits} false_positive_rate={fp}")
    print(f"sycophantic_n={fn_n} sycophantic_silent={fn_hits} false_negative_rate={fn}")
    if fp_n < 2 or fn_n < 2:
        print("FAILED:CNL-0059-probe1 corpus too small")
        return 1
    if g.get("fire") or not b.get("fire"):
        return 1

    if not ART.is_file():
        print("FAILED:CNL-0059-probe1 design artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0059-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNL-0059" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0059-probe1 sentinel absent")
        return 1
    body = O.payload(doc)
    art_fp = body.get("false_positive_rate", doc.get("false_positive_rate"))
    if type(art_fp) not in (int, float) or isinstance(art_fp, bool):
        print("FAILED:CNL-0059-probe1 artifact FP rate is not a number")
        return 1
    if abs(float(art_fp) - fp) > 1e-9:
        print(f"FAILED:CNL-0059-probe1 artifact FP {art_fp} != live {fp}")
        return 1
    bs = body.get("both_states") or doc.get("both_states") or {}
    if bs.get("known_good", {}).get("fired") is not False:
        print("FAILED:CNL-0059-probe1 artifact known_good.fired drift")
        return 1
    if bs.get("planted_bad", {}).get("fired") is not True:
        print("FAILED:CNL-0059-probe1 artifact planted_bad.fired drift")
        return 1
    print("SUCCESS:CNL-0059-probe1 both-states and false-positive-rate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
