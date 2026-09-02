#!/usr/bin/env python3
"""Named probe 2 (IMP-0155): mutated-ref record fails re-fetch (both-states).

Good state: intact record re-fetches and hash-matches.
Bad state: same record with only `ref` mutated to an existing decoy; detector
fires (HashMismatch). Field presence still holds on the mutated record, proving
acceptance is the re-fetch, not the schema of the record.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TOOLS))

import scenario as S  # noqa: E402
from foundry.provenance import (  # noqa: E402
    HashMismatch,
    mutate_ref,
    record_fields_present,
    refetch,
    refetch_report,
)


def main() -> int:
    rows = S.capture_sample(repo_root=S.REPO)
    records = S.second_agent_records(rows)
    # One posix-read and one tar-member so the detector is not method-specific.
    posix = next(r for r in records if r["retrieval_method"] == "posix-read")
    tar = next(r for r in records if r["retrieval_method"] == "tar-member")
    controls = []
    for good in (posix, tar):
        good_data = refetch(good, verify=True, repo_root=S.REPO)
        good_ok = True
        mutated = mutate_ref(good, S.decoy_ref_for(good))
        fields_on_mutated = record_fields_present(mutated)
        report = refetch_report(mutated, repo_root=S.REPO)
        fired = False
        kind = None
        try:
            refetch(mutated, verify=True, repo_root=S.REPO)
        except HashMismatch as exc:
            fired = True
            kind = "HashMismatch"
            if exc.expected == exc.actual:
                print("FAILED:IMP-0155-probe2 HashMismatch with equal hashes")
                return 1
            if exc.expected != good["hash"]:
                print("FAILED:IMP-0155-probe2 expected hash was not the recorded hash")
                return 1
        except Exception as exc:  # noqa: BLE001
            print(
                f"FAILED:IMP-0155-probe2 mutated ref raised {type(exc).__name__} "
                f"(want HashMismatch on an existing decoy): {exc}"
            )
            return 1
        if not fired:
            print("FAILED:IMP-0155-probe2 mutated ref re-fetched successfully")
            return 1
        if not fields_on_mutated:
            print("FAILED:IMP-0155-probe2 mutated record lost fields; control is vacuous")
            return 1
        if report["ok"]:
            print("FAILED:IMP-0155-probe2 refetch_report ok=true on mutated ref")
            return 1
        controls.append(
            {
                "method": good["retrieval_method"],
                "good_ref": good["ref"],
                "mutated_ref": mutated["ref"],
                "good_bytes": len(good_data),
                "good_ok": good_ok,
                "fields_present_on_mutated": fields_on_mutated,
                "fired_on_bad_state": fired,
                "silent_on_good_state": good_ok,
                "detector": kind,
                "report_error": report["error"],
            }
        )
        print(
            f"both-states method={good['retrieval_method']} good_ok={good_ok} "
            f"mutated_ref={mutated['ref']} fired={fired} detector={kind} "
            f"fields_present_on_mutated={fields_on_mutated}"
        )

    fired_all = all(c["fired_on_bad_state"] for c in controls)
    silent_all = all(c["silent_on_good_state"] for c in controls)
    doc = {
        "probe": "probe2-mutated-ref",
        "unit_id": "IMP-0155",
        "pass": fired_all and silent_all and len(controls) == 2,
        "both_states": True,
        "computed_not_asserted": True,
        "controls": controls,
        "fired_on_bad_state": fired_all,
        "silent_on_good_state": silent_all,
        "note": (
            "Mutated records still have all five fields; the detector is the "
            "re-fetch hash mismatch against the decoy bytes, not schema."
        ),
    }
    (HERE / "probe2-mutated-ref.raw.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not doc["pass"]:
        print("FAILED:IMP-0155-probe2 both-states mutated-ref control")
        return 1
    print("SUCCESS:IMP-0155-probe2 mutated-ref fails re-fetch; intact record passes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
