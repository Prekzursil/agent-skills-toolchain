#!/usr/bin/env python3
"""Probe 2: matching is semantic, not substring.

A paraphrased dissent must match. The same detector must stay silent on a
quoted mention of an exact dissent sentence (substring-matcher-too-weak).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

OUT = HERE / "probe2-semantic-not-substring.raw.json"


def main() -> int:
    dissents, full, _omitted, _disposal = A.load_control()
    by_id = {d["id"]: d for d in dissents}
    para = by_id["D-PARA"]
    quoted = by_id["D-QUOTE"]

    sub_para = A.substring_match(para["text"], full)
    sem_para = A.semantic_match(para["text"], full)
    cov_p, n_p, ov_p = A.coverage(para["text"], full)

    sub_quote = A.substring_match(quoted["text"], full)
    sem_quote = A.semantic_match(quoted["text"], full)
    cov_q, n_q, ov_q = A.coverage(quoted["text"], full)

    snap = {
        "paraphrase": {
            "id": "D-PARA",
            "substring": sub_para,
            "semantic": sem_para,
            "coverage": cov_p,
            "overlap_n": n_p,
            "overlap": sorted(ov_p),
        },
        "quoted_mention": {
            "id": "D-QUOTE",
            "substring": sub_quote,
            "semantic": sem_quote,
            "coverage": cov_q,
            "overlap_n": n_q,
            "overlap": sorted(ov_q),
        },
    }
    OUT.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        f"paraphrase substring={sub_para} semantic={sem_para} cov={cov_p:.3f} n={n_p} "
        f"quoted substring={sub_quote} semantic={sem_quote} cov={cov_q:.3f} n={n_q}"
    )
    if sub_para:
        print("FAILED:SYN-0016-probe2 paraphrase fixture is an exact substring")
        return 1
    if not sem_para:
        print("FAILED:SYN-0016-probe2 paraphrased dissent did not match")
        return 1
    if not sub_quote:
        print("FAILED:SYN-0016-probe2 quoted exact sentence missing; substring control broken")
        return 1
    if sem_quote:
        print("FAILED:SYN-0016-probe2 quoted mention matched semantically (substring-too-weak)")
        return 1
    print("SUCCESS:SYN-0016-probe2 semantic-not-substring")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
