#!/usr/bin/env python3
"""TST-0261 probe 2: empty-graph guard + Kahn leftover + contradiction handling.

  - empty_evidence (3 nodes, 0 support edges, contradiction 2-cycle):
    status NOT-CHECKED, accepted False, never ACYCLIC, no cycles claimed.
  - kahn_leftover on the 3-cycle = exactly the three claim nodes; on the
    diamond = empty.
  - the contradiction 2-cycle with zero support edges does NOT count as
    circular citation (C3).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from fixtures import DIAMOND, EMPTY_EVIDENCE, THREE_NODE_CYCLE  # noqa: E402

sys.path.insert(0, str(REPO / "tools"))
from council.evidence_graph import enforce, inspect, kahn_leftover  # noqa: E402


def main() -> int:
    checks: dict[str, bool] = {}
    emp = inspect(EMPTY_EVIDENCE)
    checks["empty_is_not_checked"] = emp["status"] == "NOT-CHECKED"
    checks["empty_not_acyclic"] = emp["status"] != "ACYCLIC"
    checks["empty_not_accepted"] = emp["accepted"] is False
    checks["empty_no_cycles_claimed"] = emp["cycles"] == []
    checks["empty_graph_size_published"] = emp["graph_size"] == {
        "nodes": 3, "edges": 2, "support_edges": 0, "contradiction_edges": 2,
    }
    checks["kahn_tri_leftover_three_nodes"] = sorted(kahn_leftover(THREE_NODE_CYCLE)) == [
        "claim-alpha", "claim-beta", "claim-gamma",
    ]
    checks["kahn_diamond_leftover_empty"] = kahn_leftover(DIAMOND) == []
    v = enforce(EMPTY_EVIDENCE)
    checks["enforce_rejects_not_checked"] = v["accepted"] is False
    v2 = enforce(THREE_NODE_CYCLE)
    checks["enforce_rejects_cycle_with_path"] = v2["accepted"] is False and "claim-alpha -> claim-beta -> claim-gamma -> claim-alpha" in v2["reason"]
    checks["enforce_accepts_diamond"] = enforce(DIAMOND)["accepted"] is True

    out = {
        "probe": "probe2_empty_and_kahn",
        "unit": "TST-0261",
        "empty_status": emp["status"],
        "kahn_tri": kahn_leftover(THREE_NODE_CYCLE),
        "kahn_diamond": kahn_leftover(DIAMOND),
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe2-empty-and-kahn.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
