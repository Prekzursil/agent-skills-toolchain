#!/usr/bin/env python3
"""Probe 2: remeasure with diff -ruN + reverse-concat tokens; independent re-sum.

Mechanically different from probe 1:
  * shell/tool: diff -ruN instead of git diff --no-index --numstat
  * token aggregation: reverse-path concat instead of per-file sum
If headline numbers diverge >10%, exit non-zero (caller must BLOCKED, not pick one).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import curve as C  # noqa: E402
import diffstat as D  # noqa: E402
import estate as E  # noqa: E402

OUT = HERE / "probe2-remeasure.raw.json"
P1 = HERE / "probe1-additions.raw.json"
BAND = 10.0


def rederive_numstat(raw: str) -> dict:
    files = 0
    ins = dele = 0
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        a, b = parts[0], parts[1]
        if a == "-" or b == "-":
            continue
        files += 1
        ins += int(a)
        dele += int(b)
    return {
        "files_touched": files,
        "lines_inserted": ins,
        "lines_deleted": dele,
        "review_surface_lines": ins + dele,
    }


def main() -> int:
    snaps = E.build_snapshots()
    t0 = snaps["t0"]
    t3 = snaps["t3"]
    uni = D.unified_diffstat(t0, t3)
    git = D.git_numstat(t0, t3)
    if uni["files_touched"] < 1 or uni["review_surface_lines"] < 1:
        print("FAILED:ARC-0004-probe2 empty unified diff")
        return 1

    c0 = C.snapshot_curve(t0)
    c3 = C.snapshot_curve(t3)
    mean_full = c3["mean_capability_tokens"]
    mean_index = c3["mean_index_tokens"]
    meta = c3["tokens_meta"]
    n_star = C.crossover_n(mean_full, mean_index, meta, activated=3)
    at_star = C.project(n_star, mean_full, mean_index, meta, 3)
    at_t3 = C.project(c3["capability_count"], mean_full, mean_index, meta, 3)
    cited = C.project(96 + 48 + 64, mean_full, mean_index, meta, 3)

    tok_sum = c3["tokens_per_file_sum"]
    tok_rev = c3["tokens_concat_reverse"]
    if not D.within_band(tok_sum, tok_rev, BAND):
        print(
            "FAILED:ARC-0004-probe2 token aggregation disagree "
            f"sum={tok_sum} reverse_concat={tok_rev}"
        )
        return 1

    files_ok = D.within_band(git["files_touched"], uni["files_touched"], BAND)
    lines_ok = D.within_band(
        git["review_surface_lines"], uni["review_surface_lines"], BAND
    )
    if not files_ok or not lines_ok:
        print(
            "FAILED:ARC-0004-probe2 git vs diff-ruN disagree "
            f"git_files={git['files_touched']} uni_files={uni['files_touched']} "
            f"git_review={git['review_surface_lines']} uni_review={uni['review_surface_lines']}"
        )
        return 1

    reviewer = None
    if P1.is_file():
        p1 = json.loads(P1.read_text(encoding="utf-8"))
        derived = {"files_touched": 0, "review_surface_lines": 0}
        for add in p1.get("additions") or []:
            row = rederive_numstat(add.get("raw_numstat") or "")
            derived["files_touched"] += row["files_touched"]
            derived["review_surface_lines"] += row["review_surface_lines"]
        author = p1.get("totals") or {}
        within = D.within_band(
            float(author.get("review_surface_lines") or 0),
            float(derived["review_surface_lines"]),
            BAND,
        ) and D.within_band(
            float(author.get("files_touched") or 0),
            float(derived["files_touched"]),
            BAND,
        )
        reviewer = {
            "reviewer_id": "ARC-0004-independent-numstat-resum",
            "independent": True,
            "author_files_touched": author.get("files_touched"),
            "author_review_surface_lines": author.get("review_surface_lines"),
            "reviewer_files_touched": derived["files_touched"],
            "reviewer_review_surface_lines": derived["review_surface_lines"],
            "band_pct": BAND,
            "within_band": within,
            "verdict": "PASS" if within else "FAIL",
        }
        if not within:
            print("FAILED:ARC-0004-probe2 independent re-sum outside 10%")
            print(json.dumps(reviewer, indent=2))
            return 1

    peer = HERE.parents[3] / "command-center/phase3/A4/COST.json"
    payload = {
        "probe": "probe2-remeasure-crossover",
        "tool": "diff-ruN-unified",
        "band_pct": BAND,
        "unified": {
            "files_touched": uni["files_touched"],
            "lines_inserted": uni["lines_inserted"],
            "lines_deleted": uni["lines_deleted"],
            "review_surface_lines": uni["review_surface_lines"],
            "files": uni["files"],
        },
        "git_t0_t3": {
            "files_touched": git["files_touched"],
            "review_surface_lines": git["review_surface_lines"],
        },
        "agreement": {
            "files_touched_pct_delta": D.pct_delta(
                git["files_touched"], uni["files_touched"]
            ),
            "review_surface_pct_delta": D.pct_delta(
                git["review_surface_lines"], uni["review_surface_lines"]
            ),
            "token_sum_vs_reverse_pct_delta": D.pct_delta(tok_sum, tok_rev),
            "within_band": True,
            "band_pct": BAND,
        },
        "curve_t0": c0,
        "curve_t3": c3,
        "crossover": {
            "catalogue_size": n_star,
            "a1_tokens": at_star["a1_tokens"],
            "gateway_tokens": at_star["gateway_tokens"],
            "measured_n": c3["capability_count"],
            "already_exceeded_at_measured_n": bool(at_t3["a1_exceeds_gateway"]),
            "cited_floors_96_48_64": cited,
            "method": (
                "A1(n)=tokens(meta)+n*mean_full_capability; "
                "gateway(n)=tokens(meta)+n*mean_index_record+3*mean_full_capability; "
                "smallest n>=1 with A1(n)>gateway(n). Means from t3 measured bytes."
            ),
        },
        "reviewer": reviewer,
        "peer_cross_check": {
            "peer_unit": "ARC-0025",
            "peer_path": "command-center/phase3/A4/COST.json",
            "peer_present": peer.is_file(),
            "result": "NOT-RUN" if not peer.is_file() else "PENDING",
        },
        "tokenizer": C.tokenizer_spec(),
    }
    if peer.is_file():
        try:
            other = json.loads(peer.read_text(encoding="utf-8"))
            peer_n = int(
                ((other.get("crossover") or {}).get("catalogue_size"))
                or ((other.get("break_even") or {}).get("catalogue_size"))
                or 0
            )
            payload["peer_cross_check"]["peer_catalogue_size"] = peer_n
            if peer_n <= 0:
                payload["peer_cross_check"]["result"] = "NOT-RUN"
                payload["peer_cross_check"]["reason"] = "peer artifact lacks catalogue_size"
            else:
                ratio = max(n_star, peer_n) / max(min(n_star, peer_n), 1)
                payload["peer_cross_check"]["ratio"] = ratio
                if ratio > 2.0:
                    print(
                        "FAILED:ARC-0004-probe2 ARC-0025 divergence "
                        f">2x local={n_star} peer={peer_n}"
                    )
                    payload["peer_cross_check"]["result"] = "FAIL"
                    OUT.write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    return 1
                payload["peer_cross_check"]["result"] = "PASS"
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            payload["peer_cross_check"]["result"] = "NOT-RUN"
            payload["peer_cross_check"]["reason"] = type(exc).__name__

    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"uni_files={uni['files_touched']} uni_review={uni['review_surface_lines']}"
        + f" git_files={git['files_touched']} git_review={git['review_surface_lines']}"
        + f" tok_sum={tok_sum} tok_rev={tok_rev}"
        + f" crossover_n={n_star}"
        + f" a1={at_star['a1_tokens']} gw={at_star['gateway_tokens']}"
        + f" exceeded_at_t3={at_t3['a1_exceeds_gateway']}"
        + f" peer={payload['peer_cross_check']['result']}"
        + f" reviewer={(reviewer or {}).get('verdict')}"
    )
    print("SUCCESS:ARC-0004-probe2 remasure, 10% band, crossover")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
