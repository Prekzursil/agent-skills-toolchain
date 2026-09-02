"""Independent both-states re-run for CNL-0086 (does not read the author's prose)."""
from __future__ import annotations

from typing import Any

import detector as D
import fixtures as F


def review() -> dict[str, Any]:
    kp_run = F.known_present()
    bad_run = F.planted_bad_shared_source()
    good_run = F.known_good_genuine_convergence()
    seq_run = F.planted_bad_sequential()
    kp = D.detect(kp_run)
    bad = D.detect(bad_run)
    good = D.detect(good_run)
    seq = D.detect(seq_run)
    ok = (
        bool(kp["fired"])
        and bool(bad["fired"])
        and (not good["fired"])
        and bool(good.get("absence_claimed"))
        and bool(seq["fired"])
        and bool(seq.get("s2_sequential_copy"))
        and (not seq.get("s1_shared_retrieval"))
        and bool(bad.get("s1_shared_retrieval"))
        and (not bad.get("s2_sequential_copy"))
    )
    return {
        "reviewer_id": "CNL-0086-both-states-rerun",
        "verdict": "PASS" if ok else "FAIL",
        "independent": True,
        "executed_both_states": True,
        "known_present_fired": bool(kp["fired"]),
        "planted_bad_fired": bool(bad["fired"]),
        "known_good_fired": bool(good["fired"]),
        "sequential_fired": bool(seq["fired"]),
        "planted_bad_s1": bool(bad.get("s1_shared_retrieval")),
        "sequential_s2": bool(seq.get("s2_sequential_copy")),
        "known_present_line": D.format_line(kp_run, kp),
        "planted_bad_line": D.format_line(bad_run, bad),
        "known_good_line": D.format_line(good_run, good),
        "sequential_line": D.format_line(seq_run, seq),
    }
