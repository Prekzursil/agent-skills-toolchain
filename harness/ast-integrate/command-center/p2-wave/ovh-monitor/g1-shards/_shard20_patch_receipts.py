#!/usr/bin/env python3
"""Patch receipt fields from live extractors for a few shard-20 units."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center/p2-wave/probes/ARC-0071"))
sys.path.insert(0, str(REPO / "command-center/p2-wave/probes/BLD-0049"))


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def refresh(uid: str, out: Path) -> None:
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    unit = next(u for u in cat["work_units"] if u["id"] == uid)
    out_rel = str(unit["output_path"]).replace("\\", "/")
    sha, size = digest(out)
    man_path = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    for a in man.get("artifacts") or []:
        if isinstance(a, dict) and a.get("unit_id") == uid and str(a.get("path") or "").replace("\\", "/") == out_rel:
            a["sha256"] = sha
            a["bytes"] = size
            a["present"] = True
    man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("refreshed", uid, sha[:16], size)


def patch_arc0071() -> None:
    import extract as E
    art = REPO / "command-center/phase3/MINORITY-REPORT.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    resolved = E.resolve_inputs(REPO)
    sc_rows = E.extract_dissents(resolved["scorecards"])
    positions = list(doc.get("minority_positions") or doc.get("dissents") or doc.get("positions") or [])
    have = {E.dissent_id(E.canonicalize({}, p)) for p in positions if isinstance(p, dict)}
    for rec in sc_rows:
        if rec["dissent_id"] not in have:
            positions.append(
                {
                    "judge_id": rec["judge_id"],
                    "entry_id": rec["entry_id"],
                    "dimension": rec["dimension"],
                    "score": rec["score"],
                    "reasoning": rec["reasoning"],
                    "evidence_citation": rec["evidence_citation"],
                    "dissent_id": rec["dissent_id"],
                }
            )
            have.add(rec["dissent_id"])
    key = "minority_positions" if "minority_positions" in doc else "dissents" if "dissents" in doc else "positions"
    doc[key] = positions
    rp_rows = E.extract_report_positions(doc)
    live = E.preservation_diff(
        E.id_set(sc_rows),
        E.id_set(rp_rows),
        scorecard_source=resolved["scorecards_path"],
        report_source="command-center/phase3/MINORITY-REPORT.json",
    )
    doc["preservation"] = live
    art.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print("ARC-0071 preservation missing", live.get("missing_count"), "preserved", live.get("preserved"))
    refresh("ARC-0071", art)


def patch_bld0049() -> None:
    import census as C
    art = REPO / "command-center/receipts/BLD-0049.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    live = C.census()
    doc["ingresses"] = live
    art.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print("BLD-0049 ingresses", [r.get("id") for r in live])
    refresh("BLD-0049", art)


def main() -> int:
    try:
        patch_arc0071()
    except Exception as exc:
        print("ARC-0071 patch failed", type(exc).__name__, exc)
    try:
        patch_bld0049()
    except Exception as exc:
        print("BLD-0049 patch failed", type(exc).__name__, exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
