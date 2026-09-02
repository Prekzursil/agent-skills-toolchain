#!/usr/bin/env python3
"""Probe 1: planted mutants, both-states, three brainstorm runs.

Recomputes live numbers and requires the catalog receipt to match.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import measure as M  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0265.json"
SENTINEL = "SUCCESS:TST-0265"


def main() -> int:
    live = M.run()
    mutants = live["planted_mutants"]
    for m in mutants:
        print(
            f"mutant class={m['class_id']} want={m['want']} "
            f"observed={m['observed']} jaccard={m['raw_jaccard']} "
            f"keys_equal={m['keys_equal']}"
        )
        if not m["passed"]:
            print(f"FAILED:TST-0265-probe1 mutant {m['class_id']} missed")
            return 1
    blind = live["blind_class"]
    print(
        f"blind class={blind['class_id']} want={blind['want']} "
        f"observed={blind['observed']} jaccard={blind['raw_jaccard']}"
    )
    if not blind["passed"]:
        print("FAILED:TST-0265-probe1 blind class did not stay SILENT")
        return 1

    both = live["both_states"]
    print(f"both_bad_verbatim={both['planted_bad']['verbatim']}")
    print(f"both_good_verbatim={both['known_good']['verbatim']}")
    print(f"both_discriminates={both['discriminates']}")
    if not both["discriminates"]:
        print("FAILED:TST-0265-probe1 both-states did not discriminate")
        return 1
    if both["known_good"]["collapse_ratio"] >= live["distinct_collapse_tolerance"]:
        print("FAILED:TST-0265-probe1 distinct corpus collapsed past tolerance")
        return 1

    if len(live["brainstorm_runs"]) != 3:
        print("FAILED:TST-0265-probe1 expected three brainstorm runs")
        return 1
    for row in live["brainstorm_runs"]:
        print(
            f"run={row['name']} raw={row['raw_count']} "
            f"post_dedup={row['post_dedup_count']} "
            f"collapse_ratio={row['collapse_ratio']}"
        )
        if row["raw_count"] != 100:
            print(f"FAILED:TST-0265-probe1 {row['name']} raw_count != 100")
            return 1

    gaming = live["gaming_simulation"]
    print(f"gaming_caught={gaming['caught']} {gaming['verbatim']}")
    if not gaming["caught"]:
        print("FAILED:TST-0265-probe1 gaming pad was not caught")
        return 1

    if not ART.is_file():
        print("FAILED:TST-0265-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0265-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0265-probe1 self-declared {doc.get('state')}")
        return 1

    art_mutants = {m["class_id"]: m for m in doc["planted_mutants"]}
    for m in mutants:
        am = art_mutants.get(m["class_id"]) or {}
        if am.get("observed") != m["observed"] or am.get("post_pair_count") != m["author_unique_count"]:
            print(f"FAILED:TST-0265-probe1 receipt mutant drift {m['class_id']}")
            return 1

    art_bad = int(doc["both_states"]["planted_bad"]["post_dedup_count"])
    art_good = int(doc["both_states"]["known_good"]["post_dedup_count"])
    if art_bad != both["planted_bad"]["post_dedup_count"]:
        print(f"FAILED:TST-0265-probe1 bad post_dedup drift art={art_bad}")
        return 1
    if art_good != both["known_good"]["post_dedup_count"]:
        print(f"FAILED:TST-0265-probe1 good post_dedup drift art={art_good}")
        return 1

    art_runs = {r["name"]: r for r in doc["brainstorm_runs"]}
    for row in live["brainstorm_runs"]:
        ar = art_runs.get(row["name"]) or {}
        if (
            int(ar.get("raw_count") or -1) != row["raw_count"]
            or int(ar.get("post_dedup_count") or -1) != row["post_dedup_count"]
        ):
            print(f"FAILED:TST-0265-probe1 brainstorm drift {row['name']}")
            return 1

    if doc.get("similarity_method") != live["similarity_method"]:
        print("FAILED:TST-0265-probe1 similarity method mismatch")
        return 1
    if float(doc.get("jaccard_threshold")) != live["jaccard_threshold"]:
        print("FAILED:TST-0265-probe1 threshold mismatch")
        return 1
    print("SUCCESS:TST-0265-probe1 mutants both-states three-runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
