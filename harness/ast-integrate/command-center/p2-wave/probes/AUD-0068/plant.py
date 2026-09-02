"""Planted-claim recall control. Fixtures must not contain PLANTED_TOKEN."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from contract import PLANTED_HEADING, PLANTED_TOKEN
from extract import extract_path


def plant_and_extract(source: Path, rel_hint: str = "scratch/planted.md") -> dict[str, Any]:
    if not source.is_file():
        return {"ok": False, "reason": "source-missing", "records": []}
    with tempfile.TemporaryDirectory(prefix="aud0068-plant-") as tmp:
        dest = Path(tmp) / source.name
        shutil.copy2(source, dest)
        extra = (
            f"\n## {PLANTED_HEADING}\n\n"
            f"CONFIRMED {PLANTED_TOKEN} the extractor must emit a canonical "
            f"record for this planted span.\n"
        )
        with dest.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(extra)
        result = extract_path(dest, rel_hint)
    hits = [
        r
        for r in result["records"]
        if PLANTED_TOKEN in r["canonical_mechanism"]
        or PLANTED_TOKEN in r["source_lineage"][0]["snippet"]
        or PLANTED_HEADING in r["canonical_mechanism"]
        or PLANTED_HEADING in r["source_lineage"][0]["snippet"]
    ]
    heading_hit = any(
        r["extension_points"]["span_kind"] == "heading" for r in hits
    )
    verdict_hit = any(
        r["extension_points"]["span_kind"] == "verdict" for r in hits
    )
    return {
        "ok": bool(hits) and verdict_hit,
        "heading_hit": heading_hit,
        "verdict_hit": verdict_hit,
        "hit_n": len(hits),
        "hit_ids": [r["claim_id"] for r in hits],
        "record_n": len(result["records"]),
        "span_n": len(result["spans"]),
    }
