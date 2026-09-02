#!/usr/bin/env python3
"""Named probe 2: one-step grant rollback (different field than probe 1).

Probe 1 reads deny-log event counts. This probe reads sha256 of the grant
snapshot versus the restored grant after a PowerShell drop.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import derive as D  # noqa: E402
import payload as P  # noqa: E402
import rollback as R  # noqa: E402
import shadow as S  # noqa: E402

ART = REPO / "command-center/phase3/A7/MIGRATION.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0049-probe2 migration artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    sample = {r["capability_id"]: r for r in P.sample_rows(doc)}
    target = sample.get(D.ROLLBACK_CAPABILITY)
    if not target:
        print("FAILED:ARC-0049-probe2 sample missing", D.ROLLBACK_CAPABILITY)
        return 1
    current = list(target.get("declared") or [])
    if D.DROP_CANDIDATE not in current:
        print("FAILED:ARC-0049-probe2 declared grant lacks", D.DROP_CANDIDATE)
        return 1
    proposed = S.drop_perm(current, D.DROP_CANDIDATE)
    result = R.rehearse(D.ROLLBACK_CAPABILITY, current, proposed)
    if not result.get("pass"):
        print("FAILED:ARC-0049-probe2 rollback rehearsal")
        print(json.dumps(result, indent=2, default=str)[:3000])
        return 1
    if not result.get("one_step") or not result.get("sha256_match"):
        print("FAILED:ARC-0049-probe2 restore was not one-step sha match")
        return 1

    recorded = P.named_test(doc, "rollback_rehearsal")
    if recorded.get("restored_capability") != D.ROLLBACK_CAPABILITY:
        print("FAILED:ARC-0049-probe2 artifact rollback path drift")
        return 1
    if recorded.get("snapshot_sha256") != result["snapshot_sha256"]:
        print("FAILED:ARC-0049-probe2 snapshot sha drift")
        print("art", recorded.get("snapshot_sha256"))
        print("live", result["snapshot_sha256"])
        return 1
    if not recorded.get("one_step") or not recorded.get("sha256_match"):
        print("FAILED:ARC-0049-probe2 artifact missing one-step match")
        return 1

    out = {
        "probe": "probe2-rollback-rehearsal",
        "unit_id": "ARC-0049",
        "restored_capability": result["restored_capability"],
        "one_step": True,
        "sha256_match": True,
        "snapshot_sha256": result["snapshot_sha256"],
        "restored_sha256": result["restored_sha256"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"restored={result['restored_capability']} "
        f"sha_match={result['sha256_match']} one_step=True"
    )
    print("SUCCESS:ARC-0049-probe2 grant snapshot rollback rehearsal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
