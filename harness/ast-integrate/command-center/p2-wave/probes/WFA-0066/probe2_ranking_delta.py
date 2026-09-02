#!/usr/bin/env python3
"""Probe 2: leverage ranking recomputed after collapse; independent 1-NN.

Reviewer method does not call discriminate(). It uses leave-one-out 1-NN on
example texts, reconstructs the pre-collapse id set from duplicate-of edges,
and checks frequency-vs-leverage disagreement on the echo cluster.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import dedup as D  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0066-mechanism-level-dedup.json"
SYN_A = "MECH-CONFLICT-REFUSE"
SYN_B = "MECH-UNION-GUARD"
SHARE_A = "MECH-SBAR-HANDOFF"
SHARE_B = "MECH-PEER-REVIEW"
ECHO = "MECH-ECHO-COPY"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0066-probe2 {msg}")
    return 1


def reconstruct(result: dict) -> set[str]:
    ids = set(result["mechanism_ids"])
    for edge in result["duplicate_of_edges"]:
        ids.add(str(edge["alias"]))
        ids.add(str(edge["canonical"]))
    return ids


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable:{exc}")
    if "SUCCESS:WFA-0066" not in text:
        return fail("sentinel absent")

    corp = C.load_corpus()
    live = D.evaluate(corp, incidence_only=False)
    orig = {str(m["id"]) for m in corp["mechanisms"]}
    if reconstruct(live) != orig:
        return fail("pre-collapse id set not reconstructible")
    if live["ids_deleted"]:
        return fail("ids were deleted")

    deltas = live["ranking_delta"]["survivor_deltas"]
    if not deltas:
        return fail("no survivor ranking delta")
    syn_delta = next(
        (
            d
            for d in deltas
            if {d["canonical_id"], d["alias_id"]} == {SYN_A, SYN_B}
        ),
        None,
    )
    if syn_delta is None:
        return fail("synonym survivor delta missing")
    if syn_delta["leverage_after"] <= syn_delta["leverage_before"]:
        return fail(
            f"leverage did not rise after collapse {syn_delta}"
        )
    if deltas[0] and live["ranking_delta"]["ranked_count_after"] != (
        live["ranking_delta"]["ranked_count_before"]
        - live["ranking_delta"]["alias_count"]
    ):
        return fail("ranked_count_after != before - alias_count")

    art_delta = (doc.get("ranking_delta") or {}).get("survivor_deltas") or []
    if not art_delta:
        return fail("artifact ranking_delta missing")
    art_syn = next(
        (
            d
            for d in art_delta
            if {d.get("canonical_id"), d.get("alias_id")} == {SYN_A, SYN_B}
        ),
        None,
    )
    if art_syn is None or art_syn.get("leverage_after") != syn_delta["leverage_after"]:
        return fail("artifact ranking_delta does not match live")

    mechs = C.mechanism_index(corp)
    knn_syn = D.example_knn_accuracy(mechs[SYN_A], mechs[SYN_B])
    knn_share = D.example_knn_accuracy(mechs[SHARE_A], mechs[SHARE_B])
    if not knn_syn["indistinguishable"]:
        return fail(f"example-1NN still split the synonym pair {knn_syn}")
    if knn_share["indistinguishable"]:
        return fail(f"example-1NN failed to split SBAR/PEER {knn_share}")

    echo = live["ranking_delta"].get("frequency_vs_leverage") or {}
    if echo.get("id") != ECHO:
        return fail("echo frequency_vs_leverage missing")
    if not echo.get("single_source"):
        return fail("echo cluster is not SINGLE-SOURCE")
    if not echo.get("disagreement"):
        return fail("frequency and leverage ranks agree on the echo; expected disagreement")
    if echo["frequency_rank_after"] >= echo["leverage_rank_after"]:
        return fail(
            "echo should rank better (lower number) on frequency than on leverage"
        )

    echo_row = next(r for r in live["all_rows_after"] if r["id"] == ECHO)
    if not echo_row["single_source"]:
        return fail("echo row missing single_source tag")

    payload = {
        "probe": "probe2-ranking-delta",
        "unit_id": "WFA-0066",
        "computed_not_asserted": True,
        "reconstructed_ids": sorted(reconstruct(live)),
        "survivor_delta": syn_delta,
        "example_knn_synonym": knn_syn,
        "example_knn_shared_source": knn_share,
        "frequency_vs_leverage": echo,
        "negative_control": {
            "fired": True,
            "what_the_check_does": (
                "example-1NN (no definitions) must fail to separate the synonym "
                "pair and must separate SBAR/PEER"
            ),
            "observed": (
                f"syn_acc={knn_syn['accuracy']} share_acc={knn_share['accuracy']}"
            ),
        },
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"ranking delta leverage {syn_delta['leverage_before']}->"
        f"{syn_delta['leverage_after']} rank {syn_delta['rank_before']}->"
        f"{syn_delta['rank_after']}"
    )
    print(
        f"echo freq_rank={echo['frequency_rank_after']} "
        f"lev_rank={echo['leverage_rank_after']} single_source={echo['single_source']}"
    )
    print(
        f"NEGATIVE-CONTROL example-1NN synonym acc={knn_syn['accuracy']} "
        f"SBAR/PEER acc={knn_share['accuracy']}"
    )
    print("SUCCESS:WFA-0066-probe2 ranking-delta and independent 1-NN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
