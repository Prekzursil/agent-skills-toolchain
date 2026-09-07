#!/usr/bin/env python3
"""AUD-0062 Probe 2: compare file-sum vs independent turn-0 occupancy instrument.

Instrument A (probe1): tiktoken (or whitespace) per-file sum.
Instrument B (this probe): byte-stat /4 occupancy over the same turn-0 full-file set,
plus AUD-0058 known_always_on channel when present.

Both-states control (catalog): omit the dominant file from the enumeration (BAD) and
confirm relative gap exceeds tolerance; complete set (GOOD) stays within tolerance.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT = PROBE / "probe2-occupancy-compare.json"
RAW = PROBE / "probe2-occupancy.raw.txt"
CTRL = PROBE / "control-tolerance.json"

TOLERANCE_FRAC = 0.35


def session_occupancy_proxy() -> dict:
    paths = [
        "CLAUDE.md",
        "AGENTS.md",
        ".agents/skills/llm-security/AGENTS.md",
        ".agents/skills/humanizer/AGENTS.md",
        ".agents/skills/code-security/AGENTS.md",
    ]
    files = []
    total_bytes = 0
    for rel in paths:
        p = REPO / rel
        if not p.is_file():
            files.append({"path": rel, "exists": False, "bytes": 0})
            continue
        b = p.stat().st_size
        total_bytes += b
        files.append({"path": rel, "exists": True, "bytes": b})

    aud58 = REPO / "command-center/audit/AUD-0058-skill-load-trigger-audit.json"
    aud58_info: dict = {"present": aud58.is_file()}
    if aud58.is_file():
        doc = json.loads(aud58.read_text(encoding="utf-8"))
        blob = json.dumps(doc)
        m = re.search(r'"known_always_on_count":\s*(\d+)', blob)
        aud58_info["known_always_on_count"] = int(m.group(1)) if m else None
        # harvest observation for skill metadata advertised at turn0
        for o in (doc.get("report") or {}).get("observations") or []:
            name = o.get("name")
            if name in (
                "known_always_on_full_files",
                "skill_metadata_advertised_at_turn0",
                "skill_full_bodies_injected_at_turn0",
            ):
                aud58_info[name] = o.get("measured")

    return {
        "method": "sum(stat.st_size of turn-0 full-file injectees)/4",
        "files": files,
        "total_bytes": total_bytes,
        "occupancy_tokens_char4": total_bytes // 4,
        "aud0058": aud58_info,
    }


def rel_gap(a: int, b: int) -> float:
    return abs(a - b) / max(a, b, 1)


def main() -> int:
    p1 = json.loads((PROBE / "probe1-tokenize-sum.json").read_text(encoding="utf-8"))
    full_items = [
        i
        for i in p1["items"]
        if i.get("exists")
        and i["kind"]
        not in (
            "skill-description-metadata",
            "skill-description-metadata-aggregate",
        )
    ]
    full_model = sum(i.get("tokens_model", i.get("tokens_whitespace", 0)) for i in full_items)
    full_c4 = sum(i["tokens_char4"] for i in full_items)
    occ = session_occupancy_proxy()
    b = occ["occupancy_tokens_char4"]

    # Cross-instrument: model tokenizer (A) vs char4 occupancy (B)
    gap_model_vs_occ = rel_gap(full_model, b)
    # Same-surface sanity: probe1 char4 vs occupancy char4 (near-identical if set complete)
    gap_c4_vs_occ = rel_gap(full_c4, b)
    within = gap_c4_vs_occ <= TOLERANCE_FRAC

    # Both-states: GOOD = complete set within tolerance
    # BAD = drop dominant file from probe1 sum → gap must exceed tolerance
    dominant = p1.get("dominant_item") or {}
    dom_c4 = int(dominant.get("tokens_char4") or 0)
    incomplete_c4 = max(0, full_c4 - dom_c4)
    bad_gap = rel_gap(incomplete_c4, b)
    fired_on_bad = bad_gap > TOLERANCE_FRAC
    silent_on_good = within

    control = {
        "id": "AUD0062-C1",
        "kind": "known-broken-fixture",
        "description": (
            "Complete injection set stays within tolerance vs occupancy; "
            "omitting the dominant file must open a gap beyond tolerance."
        ),
        "tolerance_frac": TOLERANCE_FRAC,
        "probe1_full_model": full_model,
        "probe1_full_char4": full_c4,
        "occupancy_char4": b,
        "relative_gap_c4_vs_occ": round(gap_c4_vs_occ, 4),
        "relative_gap_model_vs_occ": round(gap_model_vs_occ, 4),
        "within_tolerance": within,
        "bad_state": {
            "omitted": dominant.get("path"),
            "incomplete_char4": incomplete_c4,
            "gap": round(bad_gap, 4),
        },
        "good_state": {
            "full_char4": full_c4,
            "occupancy_char4": b,
            "gap": round(gap_c4_vs_occ, 4),
        },
        "fired_on_bad_state": fired_on_bad,
        "silent_on_good_state": silent_on_good,
        "ok": fired_on_bad and silent_on_good,
        "note": (
            "Within tolerance => file enumeration and occupancy instrument agree. "
            "Large unexplained gap => injection set incomplete — do not report as budget."
        ),
    }
    CTRL.write_text(json.dumps(control, indent=2) + "\n", encoding="utf-8")

    result = {
        "ok": control["ok"],
        "unit": "AUD-0062",
        "probe": 2,
        "probe1_full_file_tokens_model": full_model,
        "probe1_full_file_tokens_char4": full_c4,
        "probe1_total_including_skill_meta_model": p1.get(
            "total_tokens_model", p1.get("total_tokens_whitespace")
        ),
        "occupancy": occ,
        "control": control,
        "dominant_item": dominant,
        # aliases
        "probe1_full_file_tokens_whitespace": full_model,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0062 NAMED PROBE 2: occupancy instrument vs file-level sum",
        "unit=AUD-0062",
        f"tokenizer={p1.get('tokenizer')}",
        f"probe1_full_model={full_model}",
        f"probe1_full_c4={full_c4}",
        f"occupancy_c4={b}",
        f"gap_c4_vs_occ={gap_c4_vs_occ:.4f}",
        f"gap_model_vs_occ={gap_model_vs_occ:.4f}",
        f"tolerance={TOLERANCE_FRAC}",
        f"within_tolerance={within}",
        f"bad_omit_gap={bad_gap:.4f}",
        f"aud0058={json.dumps(occ['aud0058'])}",
    ]
    for f in occ["files"]:
        lines.append(f"OCC_FILE\t{f['path']}\texists={f['exists']}\tbytes={f['bytes']}")
    lines.append(
        f"CONTROL fired_bad={fired_on_bad} silent_good={silent_on_good} ok={control['ok']}"
    )
    lines.append("SUCCESS:AUD-0062-probe2")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    return 0 if control["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
