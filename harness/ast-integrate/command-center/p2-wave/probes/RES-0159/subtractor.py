#!/usr/bin/env python3
"""Novelty-net-of-briefing subtractor for RES-0159.

Declared structure is retrieved from on-disk run-record graphs
(PHASE-GRAPH.json, DEPENDENCY-GRAPH.json). Phase-0 findings are retrieved
from WORK-UNIT-CATALOG.json. This module does not reconstruct the missing
Windows Claude workflow JSON named in the harvest strike file.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CATALOG = "command-center/WORK-UNIT-CATALOG.json"
PHASE_GRAPH = "command-center/PHASE-GRAPH.json"
DEP_GRAPH = "command-center/DEPENDENCY-GRAPH.json"
OUT_REL = (
    "command-center/research/gem-hunt/"
    "RES-0159-novelty-net-of-declared-structure.json"
)
LOCAL_SCHEMA = (
    "command-center/p2-wave/probes/RES-0159/measurement-run.schema.json"
)
CATALOG_SCHEMA = "command-center/schema/measurement-run.schema.json"
SENTINEL = "SUCCESS:RES-0159"
UNIT_ID = "RES-0159"

PDF_FETCHED_AT = "2026-08-24T20:52:45Z"
PDFS = [
    (
        "kent-wep.pdf",
        "https://www.cia.gov/resources/csi/static/Words-of-Estimative-Probability.pdf",
        "Kent, Sherman. Words of Estimative Probability. Studies in Intelligence 8:4 (1964).",
    ),
    (
        "heuer-psychology.pdf",
        "https://www.cia.gov/resources/csi/static/Pyschology-of-Intelligence-Analysis.pdf",
        "Heuer, Richards J., Jr. Psychology of Intelligence Analysis. CIA CSI, 1999. CIA static filename historically misspells Psychology as Pyschology.",
    ),
    (
        "tradecraft-primer.pdf",
        "https://www.cia.gov/resources/csi/static/Tradecraft-Primer-apr09.pdf",
        "US Government. A Tradecraft Primer: Structured Analytic Techniques for Improving Intelligence Analysis (April 2009).",
    ),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def norm(token: str) -> str:
    return str(token or "").strip().upper().replace("\\", "/")


def load_json(rel: str):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def file_lineage(rel: str) -> dict:
    path = REPO / rel
    rec = {
        "path": rel,
        "present": path.is_file(),
        "retrieved_from_run_record": path.is_file(),
        "reconstructed": False,
    }
    if path.is_file():
        digest, size = sha256_file(path)
        rec.update(
            {
                "bytes": size,
                "sha256": digest,
                "mtime_utc": datetime.fromtimestamp(
                    path.stat().st_mtime, tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    return rec


@dataclass(frozen=True)
class Triple:
    subject: str
    relation: str
    object: str

    def key(self) -> tuple[str, str, str]:
        return (self.subject, self.relation, self.object)

    def as_dict(self) -> dict:
        return {
            "subject": self.subject,
            "relation": self.relation,
            "object": self.object,
        }


def triple(subject: str, relation: str, obj: str) -> Triple:
    return Triple(norm(subject), norm(relation), norm(obj))


def briefing_from_graphs() -> dict:
    phase_doc = load_json(PHASE_GRAPH)
    dep_doc = load_json(DEP_GRAPH)
    declared: set[Triple] = set()
    briefing_ids: set[str] = set()
    briefed_phases: set[str] = set()
    briefed_buckets: set[str] = set()

    for edge in phase_doc.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        frm, to = edge.get("from"), edge.get("to")
        if frm is None or to is None:
            continue
        declared.add(triple(str(frm), "PRECEDES", str(to)))
        briefing_ids.update({norm(str(frm)), norm(str(to))})
        briefed_phases.update({norm(str(frm)), norm(str(to))})

    for bucket in phase_doc.get("allocation_buckets") or []:
        if not isinstance(bucket, dict):
            continue
        bid = bucket.get("id")
        covers = bucket.get("covers_phases")
        if bid:
            briefing_ids.add(norm(str(bid)))
            briefed_buckets.add(norm(str(bid)))
        if bid is not None and covers is not None:
            declared.add(triple(str(bid), "COVERS_PHASE", str(covers)))
            for part in re.split(r"[+,]", str(covers)):
                part = part.strip()
                if part:
                    briefing_ids.add(norm(part))
                    briefed_phases.add(norm(part))

    for edge in dep_doc.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        frm, blk = edge.get("from"), edge.get("blocked_by")
        if frm is None or blk is None:
            continue
        declared.add(triple(str(frm), "BLOCKED_BY", str(blk)))
        briefing_ids.update({norm(str(frm)), norm(str(blk))})

    return {
        "declared": declared,
        "briefing_ids": briefing_ids,
        "briefed_phases": briefed_phases,
        "briefed_buckets": briefed_buckets,
        "phase_edge_count": len(phase_doc.get("edges") or []),
        "dep_edge_count": len(dep_doc.get("edges") or []),
        "bucket_count": len(phase_doc.get("allocation_buckets") or []),
    }


def phase0_units() -> list[dict]:
    catalog = load_json(CATALOG)
    units = []
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and str(unit.get("phase")) == "0":
            units.append(unit)
    return units


def findings_from_phase0(units: Iterable[dict]) -> list[Triple]:
    findings: list[Triple] = []
    for unit in units:
        uid = str(unit.get("id") or "")
        if not uid:
            continue
        for dep in unit.get("dependencies") or []:
            findings.append(triple(uid, "DEPENDS_ON", str(dep)))
        findings.append(triple(uid, "IN_PHASE", str(unit.get("phase"))))
        bucket = unit.get("bucket")
        if bucket:
            findings.append(triple(uid, "IN_BUCKET", str(bucket)))
    return findings


def plant_restatements(brief: dict, n: int = 3) -> list[Triple]:
    edges = [
        item
        for item in sorted(brief["declared"], key=lambda x: x.key())
        if item.relation == "PRECEDES"
    ]
    if len(edges) < n:
        raise RuntimeError(f"need {n} PRECEDES briefing edges, have {len(edges)}")
    return edges[:n]


def plant_novel(n: int = 3) -> list[Triple]:
    return [
        triple(f"RES0159-NOVEL-{i}", "PRECEDES", f"RES0159-NOVEL-{i}-T")
        for i in range(1, n + 1)
    ]


def is_declared(finding: Triple, brief: dict) -> bool:
    if finding in brief["declared"]:
        return True
    rel = finding.relation
    obj = finding.object
    if rel == "IN_PHASE" and obj in brief["briefed_phases"]:
        return True
    if rel == "IN_BUCKET" and obj in brief["briefed_buckets"]:
        return True
    if rel == "DEPENDS_ON" and obj in brief["briefing_ids"]:
        return True
    return False


def subtract(findings: Iterable[Triple], brief: dict) -> dict:
    raw = list(findings)
    declared_hits = [item for item in raw if is_declared(item, brief)]
    novel = [item for item in raw if not is_declared(item, brief)]
    return {
        "raw": raw,
        "declared_hits": declared_hits,
        "novel": novel,
        "raw_n": len(raw),
        "declared_n": len(declared_hits),
        "novel_n": len(novel),
    }


def recount_without_triples(units: list[dict], brief: dict) -> dict:
    """Independent integer recount. Does not construct Triple objects."""
    briefing_ids = set(brief["briefing_ids"])
    briefed_phases = set(brief["briefed_phases"])
    briefed_buckets = set(brief["briefed_buckets"])
    raw = 0
    declared = 0
    novel = 0
    by_rel: Counter[str] = Counter()
    novel_by_rel: Counter[str] = Counter()
    for unit in units:
        if not unit.get("id"):
            continue
        for dep in unit.get("dependencies") or []:
            raw += 1
            by_rel["DEPENDS_ON"] += 1
            if norm(str(dep)) in briefing_ids:
                declared += 1
            else:
                novel += 1
                novel_by_rel["DEPENDS_ON"] += 1
        raw += 1
        by_rel["IN_PHASE"] += 1
        if norm(str(unit.get("phase"))) in briefed_phases:
            declared += 1
        else:
            novel += 1
            novel_by_rel["IN_PHASE"] += 1
        bucket = unit.get("bucket")
        if bucket:
            raw += 1
            by_rel["IN_BUCKET"] += 1
            if norm(str(bucket)) in briefed_buckets:
                declared += 1
            else:
                novel += 1
                novel_by_rel["IN_BUCKET"] += 1
    return {
        "raw_n": raw,
        "declared_n": declared,
        "novel_n": novel,
        "by_rel": dict(by_rel),
        "novel_by_rel": dict(novel_by_rel),
    }


def ratio(novel_n: int, raw_n: int) -> dict:
    if raw_n <= 0:
        raise RuntimeError("raw_n=0; measurement is vacuous")
    return {
        "raw_n": raw_n,
        "novel_n": novel_n,
        "declared_n": raw_n - novel_n,
        "novel_over_raw": round(novel_n / raw_n, 6),
        "declared_over_raw": round((raw_n - novel_n) / raw_n, 6),
        "formula": "novel_n / raw_n after subtracting briefing-declared edges",
    }


def source_pdf_lineage() -> list[dict]:
    rows = []
    for name, url, cite in PDFS:
        path = HERE / "sources" / name
        rec = {
            "file": f"command-center/p2-wave/probes/RES-0159/sources/{name}",
            "resolved_url": url,
            "citation": cite,
            "fetch_timestamp_utc": PDF_FETCHED_AT,
            "present": path.is_file(),
        }
        if path.is_file():
            digest, size = sha256_file(path)
            rec.update({"sha256": digest, "bytes": size, "magic": "PDF"})
        rows.append(rec)
    return rows


def measure() -> dict:
    brief = briefing_from_graphs()
    units = phase0_units()
    findings = findings_from_phase0(units)
    result = subtract(findings, brief)
    recount = recount_without_triples(units, brief)
    plants = plant_restatements(brief, 3)
    planted_run = subtract(list(findings) + plants, brief)
    survived_plants = [item for item in plants if item in set(planted_run["novel"])]
    novels = plant_novel(3)
    novel_run = subtract(list(findings) + novels, brief)
    survived_novels = [item for item in novels if item in set(novel_run["novel"])]
    artifacts_on_disk = []
    for unit in units:
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        if not rel:
            continue
        path = REPO / rel
        if path.is_file() and path.stat().st_size > 0:
            digest, size = sha256_file(path)
            artifacts_on_disk.append(
                {
                    "unit_id": unit.get("id"),
                    "path": rel,
                    "bytes": size,
                    "sha256": digest,
                }
            )
    novel_deps = [
        item.as_dict() for item in result["novel"] if item.relation == "DEPENDS_ON"
    ]
    novel_deps.sort(key=lambda row: (row["subject"], row["object"]))
    return {
        "brief": brief,
        "units": units,
        "findings": findings,
        "result": result,
        "recount": recount,
        "plants": plants,
        "survived_plants": survived_plants,
        "novels": novels,
        "survived_novels": survived_novels,
        "mutant_skip_subtract_survived": plants,
        "artifacts_on_disk": artifacts_on_disk,
        "novel_deps": novel_deps,
        "ratio": ratio(result["novel_n"], result["raw_n"]),
        "lineage": {
            "catalog": file_lineage(CATALOG),
            "phase_graph": file_lineage(PHASE_GRAPH),
            "dependency_graph": file_lineage(DEP_GRAPH),
            "fan_out_contract": file_lineage("rules/common/fan-out-contract.md"),
            "claim_registry": file_lineage("command-center/CLAIM-REGISTRY.json"),
            "events_jsonl": file_lineage("command-center/events/EVENTS.jsonl"),
            "catalog_schema": file_lineage(CATALOG_SCHEMA),
            "windows_workflow_json": {
                "path": (
                    "C:/Users/Prekzursil/.claude/projects/"
                    "C--Users-Prekzursil/30bd50d4-5a72-4c19-8fd5-85b6430c7b7d/"
                    "workflows/wf_b7e6d4f7-7fc.json"
                ),
                "present_on_this_host": False,
                "reconstructed": False,
                "note": (
                    "Harvest named this as the exact Phase-0 payload. It is not "
                    "on this Linux worktree. Briefing used instead: live "
                    "PHASE-GRAPH.json + DEPENDENCY-GRAPH.json bytes."
                ),
            },
        },
        "pdfs": source_pdf_lineage(),
    }


def detector_ok(measured: dict) -> tuple[bool, str]:
    if len(measured["plants"]) != 3:
        return False, "need 3 planted restatements"
    if measured["survived_plants"]:
        return False, "planted restatements survived subtraction"
    if len(measured["survived_novels"]) != 3:
        return False, "novel plants were over-subtracted"
    if measured["result"]["raw_n"] != measured["recount"]["raw_n"]:
        return False, "structured raw_n != recount raw_n"
    if measured["result"]["novel_n"] != measured["recount"]["novel_n"]:
        return False, "structured novel_n != recount novel_n"
    if measured["result"]["raw_n"] < 10:
        return False, "raw_n too small for a fan-out measurement"
    return True, "ok"
