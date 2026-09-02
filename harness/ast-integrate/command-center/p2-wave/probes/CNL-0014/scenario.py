"""Live measurements shared by emit and named probes."""
from __future__ import annotations

from typing import Any

import detector as D
import fixtures as F
import selector as Sel
import store as S


def run_all() -> dict[str, Any]:
    cold_store = F.cold_start_store()
    cold_honest = Sel.rank_calibration(cold_store, F.COLD_CANDIDATES)
    cold_sets = Sel.disjoint_zero_history(cold_store, cold_honest, F.COLD_CANDIDATES)
    cold_imputed = Sel.rank_with_average_imputation(cold_store, F.COLD_CANDIDATES)
    cold_impute_sets = Sel.disjoint_zero_history(cold_store, cold_imputed, F.COLD_CANDIDATES)

    mixed = F.mixed_store()
    mixed_honest = Sel.rank_calibration(mixed, F.COLD_CANDIDATES)
    mixed_sets = Sel.disjoint_zero_history(mixed, mixed_honest, F.COLD_CANDIDATES)
    mixed_imputed = Sel.rank_with_average_imputation(mixed, F.COLD_CANDIDATES)
    mixed_impute_sets = Sel.disjoint_zero_history(mixed, mixed_imputed, F.COLD_CANDIDATES)

    both = D.both_states(mixed, mixed_honest, mixed_imputed)
    both_cold = D.both_states(cold_store, cold_honest, cold_imputed)

    good_store_errors = S.validate_store(mixed)
    invented = S.planted_invented_average_store(S.empty_store(), "alice", F.TASK)
    invented_errors = S.validate_store(invented)

    alice = S.find_record(mixed, "alice", F.TASK)
    bob = S.find_record(mixed, "bob", F.TASK)
    cara = S.find_record(mixed, "cara", F.TASK)
    ranked_ids = [row["participant_id"] for row in mixed_honest["ranked"]]
    unrankable_ids = [row["participant_id"] for row in mixed_honest["unrankable"]]

    return {
        "cold": {
            "ranked": cold_honest["ranked"],
            "unrankable": cold_honest["unrankable"],
            "ranked_count": len(cold_honest["ranked"]),
            "unrankable_count": len(cold_honest["unrankable"]),
            "switched_method": cold_honest["switched_method"],
            "sets": cold_sets,
            "imputed_ranked_count": len(cold_imputed["ranked"]),
            "imputed_overlap": cold_impute_sets["overlap"],
            "imputed_average": cold_imputed["imputed_average"],
            "impute_source": cold_imputed["impute_source"],
        },
        "mixed": {
            "ranked": mixed_honest["ranked"],
            "unrankable": mixed_honest["unrankable"],
            "ranked_ids": ranked_ids,
            "unrankable_ids": unrankable_ids,
            "sets": mixed_sets,
            "alice_brier": alice["brier"] if alice else None,
            "bob_brier": bob["brier"] if bob else None,
            "cara_resolved_n": cara["resolved_n"] if cara else None,
            "cara_rank_class": cara["rank_class"] if cara else None,
            "imputed_ranked_ids": [row["participant_id"] for row in mixed_imputed["ranked"]],
            "imputed_overlap": mixed_impute_sets["overlap"],
            "imputed_average": mixed_imputed["imputed_average"],
            "cara_beats_bob_under_imputation": _cara_beats_bob(mixed_imputed),
        },
        "both_states_mixed": both,
        "both_states_cold": both_cold,
        "store_validation": {
            "known_good_errors": good_store_errors,
            "planted_invented_errors": invented_errors,
            "known_good_accepted": good_store_errors == [],
            "planted_invented_rejected": any(
                "INVENTED_SCORE" in e or "schema:" in e for e in invented_errors
            ),
        },
        "honest_cold_not_average": (
            cold_honest["ranked"] == []
            and all(row.get("brier") is None for row in cold_honest["unrankable"])
            and cold_sets["disjoint"] is True
            and cold_honest["switched_method"] is False
        ),
        "honest_mixed_only_scored": (
            ranked_ids == ["alice", "bob"]
            and set(unrankable_ids) == {"cara", "drew"}
            and mixed_sets["disjoint"] is True
        ),
    }


def _cara_beats_bob(ranking: dict) -> bool:
    pos = {row["participant_id"]: row["rank"] for row in ranking["ranked"]}
    if "cara" not in pos or "bob" not in pos:
        return False
    return pos["cara"] < pos["bob"]


def cold_ok(m: dict) -> bool:
    return m["honest_cold_not_average"] is True and m["cold"]["ranked_count"] == 0


def mixed_ok(m: dict) -> bool:
    return m["honest_mixed_only_scored"] is True


def both_ok(m: dict) -> bool:
    mixed = m["both_states_mixed"]
    cold = m["both_states_cold"]
    return mixed["discriminates"] is True and cold["discriminates"] is True


def store_gate_ok(m: dict) -> bool:
    v = m["store_validation"]
    return v["known_good_accepted"] is True and v["planted_invented_rejected"] is True
