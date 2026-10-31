"""IMP-0154 probe1: importing the same source twice yields ONE row and a second
observation - never a duplicate candidate. Both counts are COMPUTED from the ledger.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from foundry.candidate_registry import CandidateRegistry, verify_chain  # noqa: E402

WF = {
    "id": "wf-double-import",
    "spec_version": 11,
    "units": [{"id": "u1", "prompt": "noop"}],
    "nodes": [],
}


def main() -> int:
    checks = {}
    with tempfile.TemporaryDirectory() as td:
        ledger = Path(td) / "candidates.jsonl"
        reg = CandidateRegistry(ledger)
        content = json.dumps(WF, sort_keys=True).encode("utf-8")
        r1 = reg.import_bytes("https://example.test/wf.json", content, adapter_id="imp0154")
        r2 = reg.import_bytes("https://example.test/wf.json", content, adapter_id="imp0154")
        checks["first_import_inserts"] = r1.action == "insert"
        checks["second_import_observes"] = r2.action == "observe"
        checks["same_candidate_id"] = r1.candidate_id == r2.candidate_id
        checks["row_count_is_one"] = reg.row_count() == 1
        checks["observation_count_is_two"] = (
            reg.observation_count() == 2
            and reg.observation_count("https://example.test/wf.json", r1.content_hash) == 2
        )
        snap = reg.export_snapshot()
        checks["snapshot_matches_counts"] = (
            snap["row_count"] == 1 and snap["observation_count"] == 2
        )
        checks["chain_verifies"] = verify_chain(ledger).ok
        on_disk = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
        kinds = [e["kind"] for e in on_disk]
        checks["ledger_is_append_only_jsonl"] = (
            kinds.count("candidate") == 1 and kinds.count("observation") == 2
        )

    out = {
        "unit_id": "IMP-0154",
        "probe": "probe1-double-import",
        "key": ["source_uri", "content_hash"],
        "result_1": {"action": r1.action, "candidate_id": r1.candidate_id, "row_count": r1.row_count},
        "result_2": {"action": r2.action, "candidate_id": r2.candidate_id,
                     "observation_count_for_key": r2.observation_count_for_key},
        "snapshot": snap,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0154-probe1 double import: 1 row, 2 observations, same candidate id, chain verifies")
        return 0
    print("FAILED:IMP-0154-probe1")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
