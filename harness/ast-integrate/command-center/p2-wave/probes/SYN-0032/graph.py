"""13 allocation buckets and 21 phases for SYN-0032.

PHASE-GRAPH.json is the declared home. When it is absent, reconstruct
from the live catalog: 13 id-namespace prefixes and 21 distinct phase
values. Mapping sources are published per row so a later sidecar can
supersede this reconstruction without silently renaming a lane.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PHASE_GRAPH_REL = "command-center/PHASE-GRAPH.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
SELF_ID = "SYN-0032"

# Evidence-backed prefix -> Bxx anchors. Remaining prefixes are filled
# from unused B01-B13 in min-phase then prefix order at load time only
# when PHASE-GRAPH.json does not supply allocation_buckets.
PREFIX_ANCHORS: dict[str, tuple[str, str]] = {
    "CC": ("B01", "CC-0008 catalog slice text: this file is B01"),
    "AUD": ("B02", "work_units.bucket on AUD-* rows"),
    "WFA": ("B04", "work_units.bucket on a WFA-* subset"),
    "IMP": ("B06", "IMP-0001 dependencies include B06"),
    "TST": ("B08", "TST-0236 drawn from B08 per catalog inputs"),
    "ADV": ("B10", "work_units.bucket on ADV-* rows"),
}

EXPECTED_BUCKET_IDS = tuple(f"B{i:02d}" for i in range(1, 14))
PHASE_TOKEN_RE = re.compile(r"^(\d+)([A-Z]?)$")


def phase_sort_key(phase: str) -> tuple[int, str]:
    m = PHASE_TOKEN_RE.match(str(phase))
    if not m:
        return (999, str(phase))
    return (int(m.group(1)), m.group(2) or "")


def load_work_units(catalog_path: Path) -> list[dict]:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    units = data.get("work_units") or []
    return [u for u in units if isinstance(u, dict) and isinstance(u.get("id"), str)]


def catalog_phases(units: list[dict]) -> list[str]:
    found = {str(u.get("phase")) for u in units if u.get("phase") not in (None, "")}
    return sorted(found, key=phase_sort_key)


def catalog_prefixes(units: list[dict]) -> list[str]:
    prefs = {
        uid.split("-", 1)[0]
        for u in units
        if (uid := u["id"]) and "-" in uid
    }
    return sorted(prefs)


def min_phase_for_prefix(units: list[dict], prefix: str) -> tuple[int, str, str]:
    best: tuple[int, str, str] | None = None
    for u in units:
        uid = u["id"]
        if not uid.startswith(prefix + "-"):
            continue
        ph = str(u.get("phase") or "")
        key = (*phase_sort_key(ph), ph)
        if best is None or key < best:
            best = key
    return best or (999, "Z", "")


def reconstruct_prefix_map(units: list[dict]) -> dict[str, dict]:
    prefixes = catalog_prefixes(units)
    if len(prefixes) != 13:
        raise RuntimeError(
            f"expected 13 id prefixes for 13 buckets, got {len(prefixes)}: {prefixes}"
        )
    used = {pair[0] for pair in PREFIX_ANCHORS.values()}
    remaining_ids = [b for b in EXPECTED_BUCKET_IDS if b not in used]
    remaining_prefs = [p for p in prefixes if p not in PREFIX_ANCHORS]
    remaining_prefs.sort(key=lambda p: min_phase_for_prefix(units, p) + (p,))
    if len(remaining_prefs) != len(remaining_ids):
        raise RuntimeError(
            f"prefix/bucket remainder mismatch prefs={remaining_prefs} ids={remaining_ids}"
        )
    out: dict[str, dict] = {}
    for pref, (bid, why) in PREFIX_ANCHORS.items():
        if pref not in prefixes:
            raise RuntimeError(f"anchor prefix {pref} missing from catalog")
        out[pref] = {"id": bid, "prefix": pref, "mapping_source": why}
    for pref, bid in zip(remaining_prefs, remaining_ids):
        ph = min_phase_for_prefix(units, pref)[2]
        out[pref] = {
            "id": bid,
            "prefix": pref,
            "mapping_source": (
                "reconstructed: PHASE-GRAPH.json absent; "
                f"assigned unused {bid} by min catalog phase {ph or '?'} then prefix"
            ),
        }
    by_id = {row["id"]: row for row in out.values()}
    if sorted(by_id) != list(EXPECTED_BUCKET_IDS):
        raise RuntimeError(f"bucket id set incomplete: {sorted(by_id)}")
    return out


def load_phase_graph(repo: Path) -> dict:
    path = repo / PHASE_GRAPH_REL
    catalog_path = repo / CATALOG_REL
    units = load_work_units(catalog_path)
    phases = catalog_phases(units)
    if len(phases) != 21:
        raise RuntimeError(f"expected 21 catalog phases, got {len(phases)}: {phases}")

    if path.is_file() and path.stat().st_size > 0:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            doc = None
        if isinstance(doc, dict):
            buckets = doc.get("allocation_buckets") or doc.get("buckets")
            graph_phases = doc.get("phases")
            if isinstance(buckets, list) and len(buckets) == 13:
                prefix_map = {}
                for item in buckets:
                    if not isinstance(item, dict):
                        continue
                    bid = str(item.get("id") or item.get("bucket") or "")
                    pref = str(item.get("prefix") or item.get("id_prefix") or "")
                    if bid and pref:
                        prefix_map[pref] = {
                            "id": bid,
                            "prefix": pref,
                            "mapping_source": f"{PHASE_GRAPH_REL} allocation_buckets",
                        }
                if len(prefix_map) == 13:
                    phase_ids = []
                    if isinstance(graph_phases, list) and len(graph_phases) == 21:
                        for item in graph_phases:
                            if isinstance(item, dict):
                                phase_ids.append(str(item.get("id") or item.get("phase") or ""))
                            else:
                                phase_ids.append(str(item))
                    if len(phase_ids) != 21:
                        phase_ids = phases
                    return {
                        "path": PHASE_GRAPH_REL,
                        "present": True,
                        "reconstruction": "loaded allocation_buckets and phases from sidecar",
                        "prefix_map": prefix_map,
                        "phases": phase_ids,
                        "units": units,
                    }

    prefix_map = reconstruct_prefix_map(units)
    return {
        "path": PHASE_GRAPH_REL,
        "present": False,
        "reconstruction": (
            "PHASE-GRAPH.json missing or unusable; reconstructed 13 buckets "
            "from catalog id prefixes with published anchors, and 21 phases "
            "from distinct work_units.phase values"
        ),
        "prefix_map": prefix_map,
        "phases": phases,
        "units": units,
    }


def bucket_rows_template(graph: dict) -> list[dict]:
    rows = []
    for row in graph["prefix_map"].values():
        rows.append(
            {
                "id": row["id"],
                "prefix": row["prefix"],
                "mapping_source": row["mapping_source"],
            }
        )
    rows.sort(key=lambda r: r["id"])
    return rows


def phase16_unit_ids(units: list[dict]) -> list[str]:
    ids = [
        u["id"]
        for u in units
        if str(u.get("phase")) == "16"
    ]
    ids.sort()
    return ids
