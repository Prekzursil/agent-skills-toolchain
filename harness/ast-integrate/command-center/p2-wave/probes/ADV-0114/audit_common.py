#!/usr/bin/env python3
"""ADV-0114: duplicate-mechanism collapse across the final finding set.

Probe 1 clusters by canonical-mechanism (Phase 1 field or a path-stripped
surrogate). Probe 2 is mechanically different: it clusters by remediation
equivalence, so two differently worded findings that demand the same change
collapse even when their mechanism labels differ.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "ADV-0114"
OUTPUT_REL = (
    "command-center/adversarial/"
    "ADV-0114-final-findings-mechanism-collapse.json"
)
SCHEMA_REL = "command-center/schema/refutation-record.schema.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
CLAIM_REGISTRY_REL = "command-center/CLAIM-REGISTRY.json"
P1_REL = "command-center/p2-wave/probes/ADV-0114/probe1_canonical_clusters.py"
P2_REL = "command-center/p2-wave/probes/ADV-0114/probe2_fix_equivalence.py"
P1_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P1_REL}"
P2_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P2_REL}"
LEGAL = frozenset(
    {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
)
PROBE1_NAME = (
    "Probe 1: cluster findings by canonical mechanism and report the raw "
    "count against the collapsed count, listing every cluster with more "
    "than one member."
)
PROBE2_NAME = (
    "Probe 2 (mechanically different): fix-level equivalence - two findings "
    "whose remediation is the same change are the same mechanism regardless "
    "of how differently they are described, and this catches clusters that "
    "text similarity misses."
)

# Closed sample: remesure-stable delivered artifacts, not an open glob.
SAMPLE_SOURCES = (
    "command-center/audit/AUD-0025-unpinned-version-census.json",
    "command-center/audit/AUD-0034-option-id-crossref-resolution.json",
    "command-center/audit/AUD-0052-test-order-dependence.json",
    "command-center/audit/AUD-0070-contradiction-edge-extraction.json",
    "command-center/research/RES-0009.json",
    "command-center/research/RES-0045.json",
    "command-center/research/RES-0126.json",
    "command-center/adversarial/ADV-0105-agent-independence-shared-input-audit.json",
    "command-center/adversarial/ADV-0051-clean-room-verbatim-carryover.json",
    "command-center/synthesis/SYN-0047.failure-class-coverage.json",
)

PATHISH = re.compile(r"(?:[A-Za-z0-9_.-]+/){1,}[A-Za-z0-9_.-]+")
TOKEN = re.compile(r"[a-z0-9]+")
SKIP_CATEGORIES = frozenset({"control", "negative-control", "planted"})
STRUCT_MECH_FIELDS = (
    "name",
    "ecosystem",
    "syntax_class",
    "dep_class",
    "declared",
    "category",
    "object_key",
    "namespace",
)


def load_catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UNIT_ID:
            return u
    raise RuntimeError("ADV-0114 missing from catalog")


def catalog_sentinel() -> str:
    return str(load_catalog_unit()["completion_sentinel"])


def strip_paths(text: str) -> str:
    return PATHISH.sub("<path>", text)


def slug(text: str, limit: int = 96) -> str:
    cleaned = strip_paths(text).lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned)
    return cleaned.strip("-")[:limit] or "empty"


def first_str(obj: dict, *keys: str) -> str:
    for key in keys:
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def finding_lists(doc: Any) -> list[tuple[str, list]]:
    out: list[tuple[str, list]] = []
    if not isinstance(doc, dict):
        return out
    for key in ("findings", "claims"):
        val = doc.get(key)
        if isinstance(val, list):
            out.append((key, val))
    report = doc.get("report")
    if isinstance(report, dict):
        for key in ("findings", "claims"):
            val = report.get(key)
            if isinstance(val, list):
                loc = f"report.{key}"
                if loc not in {a for a, _ in out} and key not in {a for a, _ in out}:
                    out.append((loc, val))
    return out


def mechanism_key(obj: dict, text: str) -> str:
    explicit = first_str(obj, "canonical_mechanism", "mechanism")
    if explicit:
        return slug(explicit)
    object_key = first_str(obj, "object_key")
    if object_key:
        return slug(f"object:{object_key}")
    parts = []
    for field in STRUCT_MECH_FIELDS:
        val = obj.get(field)
        if val is True:
            parts.append(f"{field}=true")
        elif val is False:
            continue
        elif isinstance(val, str) and val.strip() and field != "category":
            parts.append(f"{field}={strip_paths(val.strip())}")
    if obj.get("floats_in_practice") is True:
        parts.append("floats")
    if parts:
        cat = first_str(obj, "category")
        if cat:
            parts.insert(0, f"cat={cat}")
        return slug(":".join(parts))
    return slug(text) if text else "unspecified-mechanism"


def fix_key(obj: dict, mech: str, fid: str) -> str:
    explicit = first_str(
        obj,
        "remediation",
        "recommended_fix",
        "required_fix",
        "recommended_change",
        "fix",
        "owner_decision",
    )
    blast = obj.get("blast_radius")
    if not explicit and isinstance(blast, dict):
        explicit = first_str(blast, "if_new_major", "remediation")
    name = first_str(obj, "name")
    if explicit and name:
        return slug(f"{explicit}:{name}")
    if explicit:
        return slug(explicit)
    if name and (
        obj.get("floats_in_practice") is True
        or first_str(obj, "syntax_class") in {"range", "caret", "tilde", "wildcard"}
    ):
        declared = first_str(obj, "declared") or "unpinned"
        return slug(f"pin-exclusive-upper-bound:{name}:{declared}")
    # No shared remediation: do not invent collapse across unrelated rows.
    return slug(f"unspecified-fix:{fid}")


def files_of(obj: dict) -> list[str]:
    out: list[str] = []
    for key in ("manifest", "path", "source_path", "subject", "file"):
        val = obj.get(key)
        if isinstance(val, str) and ("/" in val or val.endswith(".py")):
            out.append(val)
    blast = obj.get("blast_radius")
    if isinstance(blast, dict):
        deps = blast.get("dependents")
        if isinstance(deps, list):
            out.extend(str(d) for d in deps if isinstance(d, str))
    return sorted(set(out))


def normalize_item(obj: dict, source_rel: str, loc: str, index: int) -> dict | None:
    if not isinstance(obj, dict):
        return None
    cat = str(obj.get("category") or "").lower()
    if cat in SKIP_CATEGORIES:
        return None
    fid = first_str(obj, "id", "claim_id", "finding_id")
    text = first_str(
        obj, "summary", "statement", "claim", "proposition", "text", "title"
    )
    if not fid and not text:
        return None
    if not fid:
        fid = f"anon-{index:03d}"
    uid = f"{Path(source_rel).stem}:{fid}"
    mech = mechanism_key(obj, text)
    fix = fix_key(obj, mech, uid)
    return {
        "id": uid,
        "native_id": fid,
        "source_path": source_rel,
        "source_loc": loc,
        "text": text or fid,
        "mechanism_key": mech,
        "fix_key": fix,
        "files": files_of(obj),
        "plant": None,
        "live": True,
        "canonical_mechanism_declared": bool(
            first_str(obj, "canonical_mechanism", "mechanism")
        ),
    }


def load_source(rel: str) -> tuple[dict | None, str]:
    path = REPO / rel
    if not path.is_file() or path.stat().st_size <= 0:
        return None, "absent"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "unparseable"
    if not isinstance(doc, dict):
        return None, "not-object"
    return doc, "ok"


def live_findings() -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    sources: list[dict] = []
    seen: set[str] = set()
    for rel in SAMPLE_SOURCES:
        doc, status = load_source(rel)
        n = 0
        if doc is not None:
            for loc, items in finding_lists(doc):
                for i, item in enumerate(items):
                    rec = normalize_item(item, rel, loc, i)
                    if rec is None or rec["id"] in seen:
                        continue
                    seen.add(rec["id"])
                    rows.append(rec)
                    n += 1
        sources.append(
            {
                "path": rel,
                "status": status,
                "present": status == "ok",
                "extracted": n,
            }
        )
    rows.sort(key=lambda r: r["id"])
    return rows, sources


def cluster(items: list[dict], key_name: str) -> list[dict]:
    groups: dict[str, list[str]] = {}
    for item in items:
        groups.setdefault(item[key_name], []).append(item["id"])
    out = []
    for key, members in sorted(groups.items()):
        members = sorted(members)
        out.append({"key": key, "size": len(members), "members": members})
    return out


def stats(clusters: list[dict], n: int) -> dict:
    multi = [c for c in clusters if c["size"] > 1]
    collapsed = len(clusters)
    ratio = 0.0 if n == 0 else round((n - collapsed) / n, 6)
    return {
        "raw": n,
        "collapsed": collapsed,
        "ratio": ratio,
        "multi_member_count": len(multi),
        "multi_member_clusters": multi,
    }


def cluster_of(clusters: list[dict], fid: str) -> str | None:
    for row in clusters:
        if fid in row["members"]:
            return row["key"]
    return None


def inflation_verdict(stat: dict) -> str:
    if stat["raw"] <= 0:
        return "NOT-CHECKED"
    if stat["multi_member_count"] > 0:
        return "CONFIRMED"
    return "REFUTED"


def measure() -> dict:
    from control_planted import overlay_plants

    live, sources = live_findings()
    plants, seed_id = overlay_plants(live)
    combined = live + plants
    p1_live = stats(cluster(live, "mechanism_key"), len(live))
    p2_live = stats(cluster(live, "fix_key"), len(live))
    p1_all = cluster(combined, "mechanism_key")
    p2_all = cluster(combined, "fix_key")
    reword_id = "ADV-0114-PLANT-REWORD"
    neigh_id = "ADV-0114-PLANT-NEIGHBOUR"
    p1_reword_key = cluster_of(p1_all, reword_id)
    p1_seed_key = cluster_of(p1_all, seed_id)
    p1_neigh_key = cluster_of(p1_all, neigh_id)
    p2_reword_key = cluster_of(p2_all, reword_id)
    p2_seed_key = cluster_of(p2_all, seed_id)
    p2_neigh_key = cluster_of(p2_all, neigh_id)
    reword_collapsed = (
        p1_reword_key is not None
        and p1_reword_key == p1_seed_key
        and p2_reword_key is not None
        and p2_reword_key == p2_seed_key
    )
    neighbour_separated = (
        p1_neigh_key is not None
        and p1_neigh_key != p1_seed_key
        and p2_neigh_key is not None
        and p2_neigh_key != p2_seed_key
    )
    by_id = {row["id"]: row for row in combined}
    seed_text = by_id[seed_id]["text"]
    neigh_text = by_id[neigh_id]["text"]
    reword_text = by_id[reword_id]["text"]
    claim_reg = REPO / CLAIM_REGISTRY_REL
    claim_present = claim_reg.is_file() and claim_reg.stat().st_size > 0
    v_canon = inflation_verdict(p1_live)
    v_fix = inflation_verdict(p2_live)
    v_reword = "CONFIRMED" if reword_collapsed else "REFUTED"
    v_neigh = "REFUTED" if neighbour_separated else "CONFIRMED"
    v_claim = "NOT-CHECKED" if not claim_present else "PARTIAL"
    targets = [
        {
            "target_id": "live:canonical-mechanism-inflation",
            "verdict": v_canon,
            "raw": p1_live["raw"],
            "collapsed": p1_live["collapsed"],
            "ratio": p1_live["ratio"],
            "multi_member_count": p1_live["multi_member_count"],
            "note": (
                "CONFIRMED means the live finding set contains duplicate "
                "canonical mechanisms once wording/file scope is ignored."
            ),
        },
        {
            "target_id": "live:fix-equivalence-inflation",
            "verdict": v_fix,
            "raw": p2_live["raw"],
            "collapsed": p2_live["collapsed"],
            "ratio": p2_live["ratio"],
            "multi_member_count": p2_live["multi_member_count"],
            "note": (
                "CONFIRMED means two or more live findings demand the same "
                "remediation change."
            ),
        },
        {
            "target_id": "control:reworded-duplicate",
            "verdict": v_reword,
            "note": (
                "CONFIRMED means the planted reworded duplicate collapsed "
                "onto the seed under both instruments."
            ),
        },
        {
            "target_id": "control:distinct-near-neighbour",
            "verdict": v_neigh,
            "note": (
                "REFUTED means the near-neighbour stayed distinct (the "
                "hypothesized false-collapse did not happen)."
            ),
        },
        {
            "target_id": "input:claim-registry",
            "verdict": v_claim,
            "present": claim_present,
            "path": CLAIM_REGISTRY_REL,
            "note": (
                "CLAIM-REGISTRY.json is the Phase-1 canonical_mechanism "
                "ledger. Absent on this worktree; not rebuilt."
            ),
        },
    ]
    live_verdicts = {
        t["verdict"]
        for t in targets
        if t["target_id"].startswith(("live:", "input:"))
    }
    if "NOT-CHECKED" in live_verdicts and len(live_verdicts) > 1:
        overall = "PARTIAL"
    elif live_verdicts == {"CONFIRMED"}:
        overall = "CONFIRMED"
    elif live_verdicts == {"REFUTED"}:
        overall = "REFUTED"
    elif live_verdicts == {"NOT-CHECKED"}:
        overall = "PARTIAL"
    else:
        overall = "PARTIAL"
    controls = {
        "both_ok": bool(reword_collapsed and neighbour_separated),
        "reword_collapsed": reword_collapsed,
        "neighbour_separated": neighbour_separated,
        "seed_id": seed_id,
        "reword_id": reword_id,
        "neighbour_id": neigh_id,
        "probe1_seed_key": p1_seed_key,
        "probe1_reword_key": p1_reword_key,
        "probe1_neighbour_key": p1_neigh_key,
        "probe2_seed_key": p2_seed_key,
        "probe2_reword_key": p2_reword_key,
        "probe2_neighbour_key": p2_neigh_key,
        "seed_text": seed_text,
        "reword_text": reword_text,
        "neighbour_text": neigh_text,
    }
    missing_sources = [s for s in sources if not s["present"]]
    return {
        "live": live,
        "plants": plants,
        "sources": sources,
        "missing_sources": missing_sources,
        "claim_registry_present": claim_present,
        "probe1": {
            "instrument": "canonical-mechanism-cluster",
            **p1_live,
        },
        "probe2": {
            "instrument": "fix-equivalence-cluster",
            **p2_live,
        },
        "controls": controls,
        "targets": targets,
        "overall_verdict": overall,
        "counts": {
            "live": len(live),
            "plants": len(plants),
            "sources_ok": sum(1 for s in sources if s["present"]),
            "sources_n": len(sources),
        },
    }


def probe1_snapshot(m: dict) -> dict:
    return {
        "instrument": "canonical-mechanism-cluster",
        "controls": {
            "both_ok": m["controls"]["both_ok"],
            "reword_collapsed": m["controls"]["reword_collapsed"],
            "neighbour_separated": m["controls"]["neighbour_separated"],
            "seed_id": m["controls"]["seed_id"],
            "probe1_seed_key": m["controls"]["probe1_seed_key"],
            "probe1_reword_key": m["controls"]["probe1_reword_key"],
            "probe1_neighbour_key": m["controls"]["probe1_neighbour_key"],
        },
        "raw": m["probe1"]["raw"],
        "collapsed": m["probe1"]["collapsed"],
        "ratio": m["probe1"]["ratio"],
        "multi_member_count": m["probe1"]["multi_member_count"],
        "multi_member_clusters": m["probe1"]["multi_member_clusters"],
        "overall_verdict": m["overall_verdict"],
        "live_verdict": next(
            t["verdict"]
            for t in m["targets"]
            if t["target_id"] == "live:canonical-mechanism-inflation"
        ),
    }


def probe2_snapshot(m: dict) -> dict:
    return {
        "instrument": "fix-equivalence-cluster",
        "controls": {
            "both_ok": m["controls"]["both_ok"],
            "reword_collapsed": m["controls"]["reword_collapsed"],
            "neighbour_separated": m["controls"]["neighbour_separated"],
            "seed_id": m["controls"]["seed_id"],
            "probe2_seed_key": m["controls"]["probe2_seed_key"],
            "probe2_reword_key": m["controls"]["probe2_reword_key"],
            "probe2_neighbour_key": m["controls"]["probe2_neighbour_key"],
        },
        "raw": m["probe2"]["raw"],
        "collapsed": m["probe2"]["collapsed"],
        "ratio": m["probe2"]["ratio"],
        "multi_member_count": m["probe2"]["multi_member_count"],
        "multi_member_clusters": m["probe2"]["multi_member_clusters"],
        "overall_verdict": m["overall_verdict"],
        "live_verdict": next(
            t["verdict"]
            for t in m["targets"]
            if t["target_id"] == "live:fix-equivalence-inflation"
        ),
    }


def probe1_report(m: dict | None = None) -> str:
    m = m or measure()
    snap = probe1_snapshot(m)
    lines = [PROBE1_NAME, json.dumps(snap, sort_keys=True, ensure_ascii=False)]
    lines.append(
        f"raw={snap['raw']} collapsed={snap['collapsed']} ratio={snap['ratio']} "
        f"multi={snap['multi_member_count']}"
    )
    for row in snap["multi_member_clusters"]:
        lines.append(
            f"cluster {row['key']} n={row['size']} "
            f"members={','.join(row['members'])}"
        )
    ctrl = m["controls"]
    lines.append(
        f"planted_reword_collapsed={ctrl['reword_collapsed']} "
        f"neighbour_separated={ctrl['neighbour_separated']} "
        f"seed={ctrl['seed_id']}"
    )
    lines.append(f"overall_verdict={m['overall_verdict']}")
    return "\n".join(lines) + "\n"


def probe2_report(m: dict | None = None) -> str:
    m = m or measure()
    snap = probe2_snapshot(m)
    lines = [PROBE2_NAME, json.dumps(snap, sort_keys=True, ensure_ascii=False)]
    lines.append(
        f"raw={snap['raw']} collapsed={snap['collapsed']} ratio={snap['ratio']} "
        f"multi={snap['multi_member_count']}"
    )
    for row in snap["multi_member_clusters"]:
        lines.append(
            f"fix-cluster {row['key']} n={row['size']} "
            f"members={','.join(row['members'])}"
        )
    ctrl = m["controls"]
    lines.append(
        f"planted_reword_collapsed={ctrl['reword_collapsed']} "
        f"neighbour_separated={ctrl['neighbour_separated']} "
        f"seed={ctrl['seed_id']}"
    )
    lines.append(
        f"overall_verdict={m['overall_verdict']} both_controls_ok={ctrl['both_ok']}"
    )
    return "\n".join(lines) + "\n"


def targets_from(m: dict) -> list[dict]:
    return list(m["targets"])
