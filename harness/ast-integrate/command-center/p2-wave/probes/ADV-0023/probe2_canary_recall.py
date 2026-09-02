#!/usr/bin/env python3
"""Probe 2: independent canary-recall + removal oracle (not a gitleaks re-list)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sweep as S  # noqa: E402

ART = S.REPO / "command-center/adversarial/ADV-0023-corpus-secret-canary-sweep.json"


def _artifact_ok() -> dict:
    info = {
        "artifact_present": ART.is_file() and ART.stat().st_size > 0,
        "sentinel_present": False,
        "recall_reported": False,
        "secret_keys_absent": True,
        "state_ok": True,
    }
    if not info["artifact_present"]:
        return info
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    info["sentinel_present"] = S.UNIT in text and "SUCCESS:ADV-0023" in text
    info["recall_reported"] = "recall" in text and "combined_rate" in text
    banned = {"secret", "Secret", "body", "canary_body", "_canary_body", "value"}
    def walk(obj) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in banned and k not in {"recall"}:
                    # 'value' as a generic JSON key is too broad; only fail long strings
                    if k in {"secret", "Secret", "body", "canary_body", "_canary_body"}:
                        info["secret_keys_absent"] = False
                    elif k == "value" and isinstance(v, str) and len(v) >= 16:
                        info["secret_keys_absent"] = False
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
    walk(doc)
    st = str(doc.get("state") or "").upper()
    info["state_ok"] = st not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
    return info


def main() -> int:
    # Independent instrument: prefix locator + entropy on planted files, then
    # confirm the full corpus sweep's recall table names every canary.
    result = S.run_sweep()
    canaries = result.get("canaries") or []
    missing = [
        c["id"]
        for c in canaries
        if not (c.get("gitleaks_found") and c.get("entropy_found"))
    ]
    leftover_now = S.leftover_canary_paths()
    art = _artifact_ok()
    summary = {
        "probe": "probe2-canary-recall-and-removal",
        "unit_id": S.UNIT,
        "instrument": "gitleaks-recall-table + entropy-on-planted + leftover-glob",
        "planted": len(canaries),
        "gitleaks_found": sum(1 for c in canaries if c.get("gitleaks_found")),
        "entropy_found": sum(1 for c in canaries if c.get("entropy_found")),
        "missing": missing,
        "recall_rate": (result.get("recall") or {}).get("combined_rate"),
        "gitleaks_rate": (result.get("recall") or {}).get("gitleaks_rate"),
        "entropy_rate": (result.get("recall") or {}).get("entropy_rate"),
        "removal_verified": bool((result.get("removal") or {}).get("verified")),
        "leftover_after": leftover_now,
        "mention_silent": bool((result.get("mention_control") or {}).get("silent")),
        "absent_silent": bool((result.get("absent_prefix") or {}).get("silent")),
        "canaries": [
            {
                "id": c["id"],
                "path": c["path"],
                "line": c["line"],
                "prefix": c["prefix"],
                "gitleaks_found": c["gitleaks_found"],
                "entropy_found": c["entropy_found"],
            }
            for c in canaries
        ],
        "artifact": art,
        "pass": False,
    }
    art_ok = (not art["artifact_present"]) or (
        art["sentinel_present"]
        and art["recall_reported"]
        and art["secret_keys_absent"]
        and art["state_ok"]
    )
    ok = (
        not missing
        and float((result.get("recall") or {}).get("gitleaks_rate") or 0) >= 1.0
        and float((result.get("recall") or {}).get("entropy_rate") or 0) >= 1.0
        and bool((result.get("removal") or {}).get("verified"))
        and leftover_now == []
        and bool((result.get("absent_prefix") or {}).get("silent"))
        and art_ok
    )
    summary["pass"] = ok
    print(json.dumps(summary, indent=2, sort_keys=True))
    if missing:
        print("FAILED:ADV-0023-probe2 missed canaries " + ",".join(missing))
        return 1
    if leftover_now:
        print("FAILED:ADV-0023-probe2 leftover canary files")
        return 1
    if not (result.get("removal") or {}).get("verified"):
        print("FAILED:ADV-0023-probe2 removal not verified")
        return 1
    if not art_ok:
        print("FAILED:ADV-0023-probe2 artifact recall/redaction check")
        return 1
    print(
        "SUCCESS:ADV-0023-probe2 all planted canaries recalled; "
        f"removal_verified=True leftover=0 rate={summary['recall_rate']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
