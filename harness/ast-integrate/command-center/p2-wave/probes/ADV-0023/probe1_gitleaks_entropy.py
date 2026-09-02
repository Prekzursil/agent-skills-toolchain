#!/usr/bin/env python3
"""Probe 1: gitleaks + Shannon entropy across the command-center corpus."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sweep as S  # noqa: E402


def main() -> int:
    result = S.run_sweep()
    recall = result.get("recall") or {}
    removal = result.get("removal") or {}
    gl = result.get("gitleaks") or {}
    summary = {
        "probe": "probe1-gitleaks-plus-entropy",
        "unit_id": S.UNIT,
        "gitleaks_exit_code": gl.get("exit_code"),
        "gitleaks_version": gl.get("version"),
        "gitleaks_hit_count": gl.get("hit_count"),
        "gitleaks_corpus_hit_count": gl.get("corpus_hit_count"),
        "entropy_hit_count": (result.get("entropy") or {}).get("hit_count"),
        "entropy_corpus_hit_count": (result.get("entropy") or {}).get("corpus_hit_count"),
        "recall": recall,
        "removal_verified": bool(removal.get("verified")),
        "leftover": removal.get("leftover") or [],
        "mention_silent": bool((result.get("mention_control") or {}).get("silent")),
        "absent_silent": bool((result.get("absent_prefix") or {}).get("silent")),
        "hits_prefix_only": True,
        "canaries": [
            {
                "id": c["id"],
                "path": c["path"],
                "line": c["line"],
                "prefix": c["prefix"],
                "gitleaks_found": c["gitleaks_found"],
                "entropy_found": c["entropy_found"],
                "entropy": c.get("gitleaks_entropy"),
            }
            for c in (result.get("canaries") or [])
        ],
        "corpus_gitleaks_hits": result.get("corpus_gitleaks_hits") or [],
        "surface_gitleaks_counts": result.get("surface_gitleaks_counts") or {},
        "pass": False,
    }
    gl_rc = gl.get("exit_code")
    ok = (
        gl_rc == 0
        and float(recall.get("combined_rate") or 0) >= 1.0
        and float(recall.get("gitleaks_rate") or 0) >= 1.0
        and bool(removal.get("verified"))
        and bool((result.get("absent_prefix") or {}).get("silent"))
        and not (removal.get("leftover") or [])
    )
    summary["pass"] = ok
    print(json.dumps(summary, indent=2, sort_keys=True))
    if gl_rc != 0:
        print("FAILED:ADV-0023-probe1 gitleaks non-zero")
        return 1
    if float(recall.get("gitleaks_rate") or 0) < 1.0:
        print("FAILED:ADV-0023-probe1 gitleaks missed a planted canary")
        return 1
    if float(recall.get("combined_rate") or 0) < 1.0:
        print("FAILED:ADV-0023-probe1 combined recall < 1")
        return 1
    if not removal.get("verified"):
        print("FAILED:ADV-0023-probe1 canaries not removed")
        return 1
    print(
        "SUCCESS:ADV-0023-probe1 gitleaks+entropy sweep; "
        f"recall={recall.get('combined_rate')} corpus_hits={gl.get('corpus_hit_count')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
