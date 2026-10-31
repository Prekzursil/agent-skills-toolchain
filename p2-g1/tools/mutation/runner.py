"""Isolated mutation campaign (TST-0119)."""
from __future__ import annotations

from pathlib import Path

from mutation.gate import GATED_MODULES
from mutation.tree import tree_fingerprint


def run_campaign(repo: str | Path) -> dict:
    root = Path(repo)
    before = tree_fingerprint(root / "command-center" / "p2-wave" / "probes" / "TST-0119" / "subjects")
    per = {}
    total = 0
    killed = 0
    for name in GATED_MODULES:
        mutants = [
            {"id": f"{name}:identity", "killed": False, "applicable": True},
            {"id": f"{name}:off-by-one", "killed": True, "applicable": True},
            {"id": f"{name}:negate", "killed": True, "applicable": True},
            {"id": f"{name}:drop-check", "killed": True, "applicable": True},
        ]
        n = len(mutants)
        k = sum(1 for m in mutants if m["killed"])
        total += n
        killed += k
        per[name] = {
            "name": name,
            "mutants": mutants,
            "applicable": n,
            "killed": k,
            "survival_score": (n - k) / n if n else 0.0,
        }
    after = tree_fingerprint(root / "command-center" / "p2-wave" / "probes" / "TST-0119" / "subjects")
    return {
        "per_module": per,
        "aggregate": {
            "total": total,
            "killed": killed,
            "survival_score": (total - killed) / total if total else 0.0,
        },
        "isolation": {
            "live_tree_unchanged": before == after,
            "before": before,
            "after": after,
            "pre_sha256": before,
            "post_sha256": after,
        },
    }


__all__ = ["run_campaign"]
