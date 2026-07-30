#!/usr/bin/env python3
"""Program E — Step 2 driver: runnability preflight for one repo. REAL Databricks spend.

Submits the runnability unit on the node (clone -> install -> run suite -> coverage -> LOCAL
commit_probe), gates it, and on DONE persists the uncovered-file gaps to e2e/_E_<repo>_gaps.json for
run_fanout.py. The artifact preview is echoed on BOTH paths, because a non-DONE verdict carries no
gaps and the node's own stdout is then the only diagnostic there is.

Needs NO github token: the node clones READ-ONLY and the probe is a LOCAL commit that is never pushed
(R1). Do NOT provision a write token for this — the push half was DELETED (`push_probe` was replaced
by `commit_probe` in harness/lanes/preflight_units.py), so provisioning one would re-expose the
fleet-wide credential this branch retires.
Run from the repo root so `from harness...` imports resolve (conftest.py adds the root to sys.path).

Both arguments are REQUIRED on purpose: this submits a billable job, so there is no default repo it
can fall back to silently.

Usage:
    python e2e/run_runnability.py env-inspector https://github.com/Prekzursil/env-inspector
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# repo root (contains harness/), so `from harness...` resolves when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.lanes import run_E

ARTIFACT_PREVIEW_CHARS = 3500


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print("usage: run_runnability.py <repo> <clone_url>", file=sys.stderr)
        return 2
    repo, clone_url = argv[0], argv[1]
    ok, gaps, text = run_E.runnability(repo, clone_url)
    print(f"RUNNABILITY {repo} ok={ok} gaps={len(gaps)}")
    out = Path(__file__).resolve().parent / f"_E_{repo}_gaps.json"
    out.write_text(
        json.dumps({"repo": repo, "ok": ok, "gaps": gaps}, indent=2), encoding="utf-8"
    )
    print(f"=== artifact (first {ARTIFACT_PREVIEW_CHARS} chars) ===")
    print((text or "(empty)")[:ARTIFACT_PREVIEW_CHARS])
    if not ok:
        print(f"FAILED: runnability preflight for {repo} did not reach DONE")
        return 1
    print(f"SUCCESS: runnability {repo} -> {len(gaps)} uncovered-file gap(s) -> {out}")
    for g in gaps:
        print(f"  gap: {g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
