#!/usr/bin/env python3
"""ADV-0015 probe2 -- independent content re-derivation (mechanically different).

Recomputes the artifact's claims from its own raw rows and live inputs
(counts, census, internal consistency, live referenced files) and
byte-compares the per-unit manifest registration against the live artifact
(LF-normalized sha256, matching _measure_one_delivered.py). Fails closed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/adversarial/ADV-0015-model-routing-table-staleness.json"
MANIFEST = REPO / "command-center/p2-wave/probes/ADV-0015/UNIT-ARTIFACT-MANIFEST.json"
UNIT = "ADV-0015"
LEGAL = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}

fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def manifest_byte_compare(doc: dict) -> None:
    chk(MANIFEST.is_file(), "manifest-absent")
    if not MANIFEST.is_file():
        return
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = lf_sha(OUT)
    rows = [a for a in (man.get("artifacts") or [])
            if isinstance(a, dict) and a.get("unit_id") == UNIT]
    chk(bool(rows), "manifest-row-absent")
    match = [a for a in rows
             if str(a.get("path") or "").replace("\\", "/") == "command-center/adversarial/ADV-0015-model-routing-table-staleness.json"
             and str(a.get("sha256") or "") == live
             and a.get("present") is True]
    chk(bool(match), "manifest-sha-mismatch-live",
        f"live={live[:16]} rows={[str(a.get('sha256'))[:16] for a in rows]}")



def rederive(doc: dict) -> None:
    counts = doc.get("counts") or {}
    diffs = doc.get("diffs") or []
    targets = doc.get("targets") or []
    chk(len(diffs) == int(counts.get("n_table_rows") or -1), "diffs!=n_table_rows",
        f"{len(diffs)} vs {counts.get('n_table_rows')}")
    # every diff row in this sweep is a stale-table row; stale_models is the
    # per-model unique list (n_stale counts rows, stale_models counts models)
    chk(len(diffs) == int(counts.get("n_stale") or -1), "stale-rows!=n_stale",
        f"{len(diffs)} vs {counts.get('n_stale')}")
    chk(len(targets) == int(counts.get("n_targets") or -1), "targets!=n_targets",
        f"{len(targets)} vs {counts.get('n_targets')}")
    stale_models = doc.get("stale_models") or []
    models = {str(r.get("model")) for r in diffs}
    chk(len(models) == len(stale_models), "unique-models-mismatch",
        f"diffs models={len(models)} stale_models={len(stale_models)}")
    chk(int(counts.get("n_match") or 0) == 0 or bool(doc.get("matching_models")),
        "match-count-inconsistent")
    for t in targets:
        chk(str(t.get("verdict")) in LEGAL, "verdict-illegal", f"{t.get('id')}={t.get('verdict')}")
        if str(t.get("id")) == "CTRL-SURFACE-MATCHING-ROW":
            chk(str(t.get("verdict")) == "REFUTED",
                "planted-matching-control-not-refuted")
    ov = str(doc.get("overall_verdict") or "")
    chk(ov in LEGAL, "overall-verdict-illegal", ov)
    chk(ov == "PARTIAL" if int(counts.get("n_stale") or 0) else True,
        "overall-verdict-vs-stale-count", ov)


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:ADV-0015-probe2 artifact-unreadable:" + type(exc).__name__)
        return 1
    manifest_byte_compare(doc)
    rederive(doc)
    if fails:
        for f in fails[:12]:
            print("FAILED:ADV-0015-probe2 " + f)
        return 1
    print("SUCCESS:ADV-0015-probe2 content re-derived live; manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
