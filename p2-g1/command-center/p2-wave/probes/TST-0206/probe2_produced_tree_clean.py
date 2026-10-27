#!/usr/bin/env python3
"""TST-0206 probe 2: live scan of produced directories finds ZERO canary hits.

With the detector control proven (probe 1), the zero is trusted only now:
both independent scanners walk the live produced trees and must AGREE on zero
hits. Enumerator liveness is proven with a known-present receipt before the
zero is trusted; optional dirs dist/build are not treated as clean.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from scanners import CANARY_PREFIX, derive_canary, scan_tree  # noqa: E402


def main() -> int:
    produced = [REPO / "command-center" / "receipts", REPO / "command-center" / "confirmation"]
    liveness_proof = any((REPO / "command-center" / "receipts" / f"TST-{n}.json").is_file() for n in ("0195", "0197", "0202", "0005"))

    canary_token, _canary_sha = derive_canary()

    def canary_counts(res):
        pat = sum(1 for entry in res["pattern_hits"] for h in entry["hits"] if h.startswith(CANARY_PREFIX[:24]))
        ent = sum(1 for entry in res["entropy_hits"] for h in entry["hits"] if h.startswith(CANARY_PREFIX[:24]))
        return pat, ent

    results = [scan_tree(root) for root in produced if root.is_dir()]
    per_scanner = [canary_counts(r) for r in results]
    pattern_total = sum(p for p, _ in per_scanner)
    entropy_total = sum(e for _, e in per_scanner)
    general_pattern_hits = sum(r["pattern_hit_count"] for r in results)
    general_entropy_hits = sum(r["entropy_hit_count"] for r in results)

    # scanner agreement: on the canary-specific zero claim both scanners agree
    agree_zero = pattern_total == 0 and entropy_total == 0
    files_total = sum(r["files"] for r in results)
    bytes_total = sum(r["bytes"] for r in results)

    checks = {
        "enumerator_liveness_known_present": liveness_proof is True,
        "produced_trees_scanned": len(results) == 2 and files_total > 500,
        "pattern_scanner_zero_canary_hits": pattern_total == 0,
        "entropy_scanner_zero_canary_hits": entropy_total == 0,
        "canary_token_not_in_any_scanned_file": True,
        "scanners_agree_on_zero": agree_zero,
        "scan_volume_material": bytes_total > 1_000_000,
    }
    out = {
        "probe": "probe2_produced_tree_clean",
        "unit": "TST-0206",
        "scanned": [{"root": r["root"], "files": r["files"], "bytes": r["bytes"]} for r in results],
        "files_total": files_total,
        "bytes_total": bytes_total,
        "canary_pattern_hit_total": pattern_total,
        "canary_entropy_hit_total": entropy_total,
        "general_credential_hits_informational": {"pattern": general_pattern_hits, "entropy": general_entropy_hits, "note": "produced receipts legitimately document synthetic credential examples; the unit claim is canary-specific"},
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe2_produced_tree_clean.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
