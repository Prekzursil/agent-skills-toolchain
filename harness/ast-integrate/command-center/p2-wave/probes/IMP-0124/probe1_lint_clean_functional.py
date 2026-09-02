"""Named probe 1: restored registry is lint-clean and functionally equivalent.

Signal 1: index linter over the restored copy reports zero blocking findings
          (the linter walks the blob store, not only the index).
Signal 2: resolve + install + verify of echo-skill@1.0.1 succeeds against the
          restored copy. Structural validity and functional equivalence are
          different claims; both must hold.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.drill import scratch_restore_drill  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0124-p1-") as raw:
        report = scratch_restore_drill(Path(raw))
    payload = {
        "pass": bool(report["ok"]),
        "probe": "probe1-lint-clean-functional",
        "unit_id": "IMP-0124",
        "lint_ok": report["lint"]["ok"],
        "blocking_findings": report["lint"]["blocking"],
        "walked_blob_store": report["lint"]["walked_blob_store"],
        "functional_ok": report["functional"]["ok"],
        "probe_package": report["probe_package"],
        "packages_equal": report["packages_equal"],
        "event_chain_ok": report["event_chain"]["ok"],
        "live_snapshot_unchanged": report["live_snapshot_unchanged"],
        "census_hits_live": report["census_hits_live"],
        "package_count": report["package_count"],
    }
    print(json.dumps(payload, sort_keys=True))
    if not report["ok"]:
        print("FAILED:IMP-0124-probe1 scratch restore was not lint-clean and functional")
        return 1
    print(
        "lint_ok=True functional_ok=True packages_equal=True "
        f"walked_blobs={report['lint']['walked_blob_store']} "
        f"pkg={report['probe_package']}"
    )
    print("SUCCESS:IMP-0124-probe1 restored registry lint-clean and functional")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
