#!/usr/bin/env python3
"""Probe 1: live three-way table. Windows-specific must DIVERGE; portable must AGREE.

Every cell cites a run id or container digest. CI cells are filled from the
run record's conclusion field, not from ci-summary.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from container import is_floating_ref  # noqa: E402
from matrix import build_live, dump  # noqa: E402

OUT = HERE / "probe1-three-way.raw.json"
ART = REPO / "command-center/receipts/CNF-0151.json"


def check_artifact(live: dict) -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return None
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0151":
        return f"unit_id={doc.get('unit_id')}"
    if "SUCCESS:CNF-0151" not in json.dumps(doc):
        return "sentinel-absent"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{st}"
    matrix = doc.get("matrix") or []
    if len(matrix) < 4:
        return f"matrix-rows={len(matrix)}"
    port = [r for r in matrix if r.get("class") == "portable"]
    win = [r for r in matrix if r.get("class") == "windows-specific"]
    if not port or any(r.get("agreement") != "AGREE" for r in port):
        return "portable-not-agree"
    if not win or any(r.get("agreement") != "DIVERGE" for r in win):
        return "windows-specific-not-diverge"
    for row in matrix:
        for col, cell in (row.get("cells") or {}).items():
            if not cell.get("run_id") and not cell.get("digest"):
                return f"cell-missing-evidence {row.get('claim_id')} {col}"
    img = doc.get("image") or {}
    if is_floating_ref(str(img.get("ref") or "")) or img.get("floating_tag") is True:
        return "floating-tag"
    if not (doc.get("ci_evidence") or {}).get("stale_summary_rejected"):
        return "ci-stale-not-rejected"
    live_port = [r["claim_id"] for r in live["matrix"] if r["portable"] and r["agreement"] == "AGREE"]
    art_port = [r["claim_id"] for r in port if r.get("agreement") == "AGREE"]
    if live_port != art_port:
        return f"artifact-live-portable-mismatch {live_port} {art_port}"
    return None


def main() -> int:
    live = build_live(nonce="probe1")
    dump(OUT, live)
    if not live.get("pass"):
        print("FAILED:CNF-0151-probe1 live matrix controls")
        print(json.dumps({k: live.get(k) for k in ("portable_agree", "windows_specific_diverges", "container_host_cache_visible", "pass")}, sort_keys=True))
        return 1
    if is_floating_ref(live["image"]["ref"]):
        print("FAILED:CNF-0151-probe1 floating image ref")
        return 1
    if not live["ci"]["stale_differs"] or live["ci"]["used_source"] != "run.conclusion":
        print("FAILED:CNF-0151-probe1 CI conclusion not re-read from run")
        return 1
    art_err = check_artifact(live)
    if art_err:
        print(f"FAILED:CNF-0151-probe1 artifact {art_err}")
        return 1
    print(
        "portable_agree="
        + str(live["portable_agree"])
        + " windows_specific_diverges="
        + str(live["windows_specific_diverges"])
        + " host_cache_visible="
        + str(live["container_host_cache_visible"])
        + " image="
        + live["image"]["ref"]
        + " ci_source="
        + live["ci"]["used_source"]
        + " stale_differs="
        + str(live["ci"]["stale_differs"])
    )
    for row in live["matrix"]:
        v = row["verdicts"]
        print(
            f"  {row['claim_id']} class={row['class']} agreement={row['agreement']} "
            f"win={v['windows-box']} ctr={v['linux-container']} ci={v['ci']}"
        )
    print("SUCCESS:CNF-0151-probe1 three-way portable vs windows-specific matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
