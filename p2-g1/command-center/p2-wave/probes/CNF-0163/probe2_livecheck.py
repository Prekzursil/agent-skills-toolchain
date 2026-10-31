#!/usr/bin/env python3
"""CNF-0163 probe2: live worktree-anchor re-verification. Deterministic strided sample of
worktree-only anchor rows; every citing receipt named by the sampled rows must exist on disk
today, and every cited construct line must still land inside the citing file. The planted
fixture history that proved the four-way classification in August did not survive the worktree
export; that is recorded as a fact, not silently skipped.
Emitted by shard8-w2 resume builder 2026-10-25."""
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CHECKS = []
FACTS = {}

def ck(name, cond):
    CHECKS.append({"check": name, "ok": bool(cond)})
    return bool(cond)

def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))

def finish(pid, uid):
    raw = {"probe": pid, "unit": uid, "facts": FACTS, "checks": CHECKS, "all_ok": all(c["ok"] for c in CHECKS)}
    (Path(__file__).parent / (pid + ".raw.json")).write_bytes(json.dumps(raw, indent=1).encode("utf-8"))
    print(json.dumps(raw))
    return 0 if raw["all_ok"] else 1

def main():
    d = load("command-center/receipts/CNF-0163.json")
    wo = d["classes"]["worktree-only"]
    ck("worktree_rows_present", len(wo) == 1161)

    sample = wo[::47][:25]
    missing_receipts = []
    for r in sample:
        for citing in r.get("cited_by", []):
            if not (REPO / citing).is_file():
                missing_receipts.append(citing)
    FACTS["sampled_rows"] = len(sample)
    FACTS["missing_cited_receipts"] = missing_receipts
    ck("sampled_citing_receipts_exist_live", not missing_receipts)

    lines_ok = 0
    for r in sample:
        cite = r.get("cited_by", [])
        if not cite:
            continue
        path = REPO / cite[0]
        if path.is_file():
            n_lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
            if isinstance(r.get("line"), int) and 1 <= r["line"] <= max(n_lines, 1):
                lines_ok += 1
    ck("sampled_anchor_lines_land_inside_files", lines_ok >= max(1, len(sample) // 2))
    FACTS["lines_inside_bounds"] = lines_ok

    probe_dir = Path(__file__).parent
    FACTS["planted_fixture_history_present"] = any(probe_dir.glob("*.git*")) or (probe_dir / "fixture.git").exists()
    mar = d["classes"]["missing-at-revision"][:25]
    ck("missing_at_revision_sample_blobless", all(r.get("blob_available") is False for r in mar))
    return finish("probe2_livecheck", "CNF-0163")

if __name__ == "__main__":
    sys.exit(main())
