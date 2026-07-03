"""E2E smoke test for the schrodinger MCP — exercises the real tools against the local
Schrodinger Suite. Writes to a throwaway temp dir (repo stays clean). Read-only on the repo.

  smiles_to_3d (RDKit, license-free) -> qikprop_admet (consumes a license token)

This proves the license-token driver path (_driver + -WAIT + _exec) that ALL the product
drivers share (ligprep / qikprop / glide / glide_grid / prepwizard / prime_mmgbsa).

Run:  .venv\\Scripts\\python.exe _e2e_test.py
"""
from __future__ import annotations

import os
import tempfile

import server  # the tools are plain callables after @mcp.tool()

WARFARIN = "CC(=O)CC(c1ccccc1)c1c(O)c2ccccc2oc1=O"


def main() -> int:
    ws = tempfile.mkdtemp(prefix="sch_e2e_")
    mae = os.path.join(ws, "warfarin.mae")
    print(f"[ws] {ws}")

    r1 = server.smiles_to_3d(WARFARIN, mae, "warfarin")
    print("[smiles_to_3d]", {k: r1.get(k) for k in ("out_path", "atoms", "error")} if isinstance(r1, dict) else r1)
    if not os.path.exists(mae):
        print("VERDICT: FAIL (warfarin.mae not produced)")
        return 1

    r2 = server.qikprop_admet(mae, timeout_s=600)
    keys = ("returncode", "csv", "error")
    print("[qikprop_admet]", {k: r2.get(k) for k in keys} if isinstance(r2, dict) else r2)
    if isinstance(r2, dict) and r2.get("csv_head"):
        print("[qikprop csv head]", r2["csv_head"][:300])

    ok = isinstance(r2, dict) and r2.get("csv") and os.path.exists(r2["csv"])
    print("VERDICT:", "PASS (qikprop produced a result CSV)" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
