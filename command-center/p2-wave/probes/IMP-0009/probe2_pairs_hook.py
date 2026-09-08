#!/usr/bin/env python3
"""IMP-0009 probe2: object_pairs_hook preserves Name/name; plain dict destroys exact dups."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import manifest_schema as M  # noqa: E402

PROBE = Path(__file__).resolve().parent
EVIDENCE = (
    "TWO independent signals: (1) the linter flags a fixture with `Name`/`name`; "
    "(2) a raw byte-level key extraction (json.loads with object_pairs_hook, which "
    "preserves duplicates) independently confirms both keys were present in the "
    "source — because a naive dict load would have already destroyed the evidence."
)


def main() -> int:
    live_raw = (REPO / M.MANIFEST_RELPATH).read_text(encoding="utf-8")
    case_planted = M.mutate_case_collision_text(live_raw)
    exact_planted = M.mutate_duplicate_key_text(live_raw)

    # Signal (2): pairs hook sees both Name and name.
    case_keys = M.top_level_key_occurrences(case_planted)
    case_hits = M.find_case_collisions(case_keys)
    pairs_sees_both = any(
        a.casefold() == "name" and b.casefold() == "name" and a != b
        for a, b in case_hits
    ) or (
        "Name" in case_keys
        and "name" in case_keys
        and case_keys.count("Name") + case_keys.count("name") >= 2
    )

    # Exact-duplicate control: pairs hook preserves two "name"; plain dict collapses.
    exact_keys = M.top_level_key_occurrences(exact_planted)
    pairs_exact_count = exact_keys.count("name")
    naive_exact = json.loads(exact_planted)
    naive_exact_count = list(naive_exact.keys()).count("name")
    plain_dict_destroys_exact = pairs_exact_count >= 2 and naive_exact_count == 1

    # Case-insensitive fold would also destroy Name/name identity.
    folded_idents = {k.casefold() for k in case_keys}
    casefold_collapse = (
        len([k for k in case_keys if k.casefold() == "name"]) >= 2
        and "name" in folded_idents
    )

    confirmed = bool(pairs_sees_both and plain_dict_destroys_exact and casefold_collapse)

    meas = {
        "probe": "probe2-pairs-hook-preserves",
        "probe_2_confirmed": confirmed,
        "ok": confirmed,
        "pairs_sees_name_and_Name": pairs_sees_both,
        "case_keys_sample": [k for k in case_keys if k.casefold() == "name"],
        "case_collisions": [{"a": a, "b": b} for a, b in case_hits],
        "exact_pairs_name_count": pairs_exact_count,
        "exact_naive_dict_name_count": naive_exact_count,
        "plain_dict_destroys_exact_duplicate_evidence": plain_dict_destroys_exact,
        "casefold_would_collapse": casefold_collapse,
        "loader": "json.loads(..., object_pairs_hook=extract_object_key_occurrences)",
        "naive_loader": "json.loads (plain dict)",
    }
    (PROBE / "probe2-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "NAMED PROBE 2: object_pairs_hook PRESERVES DUPLICATES",
        "PROBE-2-BEGIN:IMP-0009",
        "stage=p2-deliver",
        f"evidence_requirement_verbatim={EVIDENCE}",
        f"pairs_sees_name_and_Name={pairs_sees_both}",
        f"exact_pairs_name_count={pairs_exact_count}",
        f"exact_naive_dict_name_count={naive_exact_count}",
        f"plain_dict_destroys_exact_duplicate_evidence={plain_dict_destroys_exact}",
        f"casefold_would_collapse={casefold_collapse}",
        f"probe_2_confirmed={confirmed}",
        "PROBE-2-COMPLETE:IMP-0009",
        "SUCCESS:IMP-0009-probe2" if confirmed else "FAILED:IMP-0009-probe2",
    ]
    raw = "\n".join(lines) + "\n"
    (PROBE / "probe2-pairs-hook.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if confirmed else 1


if __name__ == "__main__":
    raise SystemExit(main())
