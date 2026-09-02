"""Join 13 buckets and 21 phases to receipts and synthesis mentions."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from graph import (
    CATALOG_REL,
    SELF_ID,
    bucket_rows_template,
    load_phase_graph,
    phase16_unit_ids,
)
from mentions import body_text_for_path, body_text_for_string, count_tokens

RECEIPT_STEM = re.compile(r"^([A-Z]{2,5})-\d{4}$")
RECEIPTS_REL = "command-center/receipts"
SYNTHESIS_DIRS = (
    "command-center/synthesis",
    "command-center/syntheses",
)


def verdict(receipts: int, mentions: int) -> str:
    if mentions > 0:
        return "REPRESENTED"
    if receipts > 0:
        return "RECEIPTS-ONLY"
    return "ABSENT"


def tally(values: list[str]) -> dict[str, int]:
    counts = Counter(values)
    return {
        "REPRESENTED": int(counts.get("REPRESENTED", 0)),
        "RECEIPTS-ONLY": int(counts.get("RECEIPTS-ONLY", 0)),
        "ABSENT": int(counts.get("ABSENT", 0)),
    }


def list_receipt_paths(receipts_dir: Path, exclude: frozenset[str]) -> list[Path]:
    if not receipts_dir.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(receipts_dir.glob("*.json")):
        if path.stem in exclude:
            continue
        if not RECEIPT_STEM.match(path.stem):
            continue
        if path.stat().st_size <= 0:
            continue
        out.append(path)
    return out


def discover_synthesis(repo: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for rel in SYNTHESIS_DIRS:
        root = repo / rel
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".md", ".json", ".txt"}:
                continue
            found.append(
                (
                    str(path.relative_to(repo)).replace("\\", "/"),
                    path.read_text(encoding="utf-8"),
                )
            )
    return found


def compute_coverage(
    repo: Path,
    *,
    receipts_dir: Path | None = None,
    synthesis_docs: list[tuple[str, str]] | None = None,
    exclude_receipts: frozenset[str] | None = None,
) -> dict:
    graph = load_phase_graph(repo)
    prefix_map: dict[str, dict] = graph["prefix_map"]
    prefix_to_bucket = {pref: row["id"] for pref, row in prefix_map.items()}
    units: list[dict] = graph["units"]
    unit_by_id = {u["id"]: u for u in units}
    phases: list[str] = list(graph["phases"])

    exclude = frozenset(exclude_receipts or {SELF_ID})
    receipts_root = receipts_dir if receipts_dir is not None else repo / RECEIPTS_REL
    receipt_paths = list_receipt_paths(receipts_root, exclude)

    bucket_receipts = {row["id"]: 0 for row in bucket_rows_template(graph)}
    phase_receipts = {ph: 0 for ph in phases}
    receipt_ids_by_phase: dict[str, list[str]] = {ph: [] for ph in phases}

    for path in receipt_paths:
        stem = path.stem
        match = RECEIPT_STEM.match(stem)
        if not match:
            continue
        pref = match.group(1)
        bid = prefix_to_bucket.get(pref)
        if bid:
            bucket_receipts[bid] += 1
        unit = unit_by_id.get(stem)
        if unit is not None:
            ph = str(unit.get("phase") or "")
            if ph in phase_receipts:
                phase_receipts[ph] += 1
                receipt_ids_by_phase[ph].append(stem)

    if synthesis_docs is None:
        synthesis_docs = discover_synthesis(repo)

    bucket_mentions = {bid: 0 for bid in bucket_receipts}
    phase_mentions = {ph: 0 for ph in phases}
    synthesis_paths: list[str] = []
    for loc, text in synthesis_docs:
        synthesis_paths.append(loc)
        kind = "json" if loc.endswith(".json") else "markdown"
        disk = Path(loc)
        if disk.is_file():
            body = body_text_for_path(disk)
        else:
            body = body_text_for_string(text, kind)
        bcounts, pcounts = count_tokens(body, prefix_to_bucket)
        for bid, n in bcounts.items():
            if bid in bucket_mentions:
                bucket_mentions[bid] += n
        for ph, n in pcounts.items():
            if ph in phase_mentions:
                phase_mentions[ph] += n

    bucket_table = []
    for row in bucket_rows_template(graph):
        bid = row["id"]
        rc = bucket_receipts[bid]
        mc = bucket_mentions[bid]
        bucket_table.append(
            {
                "id": bid,
                "prefix": row["prefix"],
                "receipt_count": rc,
                "synthesis_mention_count": mc,
                "verdict": verdict(rc, mc),
                "mapping_source": row["mapping_source"],
            }
        )

    phase_table = []
    for ph in phases:
        rc = phase_receipts[ph]
        mc = phase_mentions[ph]
        phase_table.append(
            {
                "id": ph,
                "receipt_count": rc,
                "synthesis_mention_count": mc,
                "verdict": verdict(rc, mc),
                "has_allocation_bucket": ph != "16",
            }
        )

    p16_units = phase16_unit_ids(units)
    p16_receipts = list(receipt_ids_by_phase.get("16") or [])
    funded = {
        "note": (
            "Phase 16 is the only catalog phase with no allocation bucket "
            "(unfunded lane). Funded-by covering units from "
            f"{CATALOG_REL} phase=16: "
            + ", ".join(p16_units)
            + ". Live receipts for those units on this worktree: "
            + (", ".join(p16_receipts) if p16_receipts else "none")
            + ". TST-0236 is catalogued as drawn from B08 as the recommended home."
        ),
        "unit_ids": p16_units,
        "allocation_bucket": None,
        "receipt_ids": p16_receipts,
    }

    return {
        "graph": graph,
        "bucket_table": bucket_table,
        "phase_table": phase_table,
        "phase_16_funded_by": funded,
        "receipts_scanned": [p.name for p in receipt_paths],
        "receipts_dir": str(receipts_root).replace("\\", "/"),
        "synthesis_paths": synthesis_paths,
        "self_receipt_excluded": True,
        "verdict_counts": {
            "buckets": tally([r["verdict"] for r in bucket_table]),
            "phases": tally([r["verdict"] for r in phase_table]),
        },
    }
