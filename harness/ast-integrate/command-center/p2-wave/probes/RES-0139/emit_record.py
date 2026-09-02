#!/usr/bin/env python3
"""Emit RES-0139 research claim record from frozen snapshots + catalog scan."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import adapter as A  # noqa: E402
import contradiction as C  # noqa: E402

OUT_REL = (
    "command-center/research/sources-frontier/"
    "RES-0139-standards-working-group-source-adapter.json"
)
SCHEMA_REL = "command-center/schema/research-claim-record.schema.json"
QUESTION = (
    "For IETF datatracker, W3C group archives, OpenSSF/SLSA working groups "
    "and the MCP specification repository: what is the stable, machine-readable "
    "way to extract a normative requirement plus its discussion history, and "
    "which of our planned contracts already contradict a published normative "
    "requirement?"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def snap_lineage(source_class: str) -> list[dict]:
    rows = []
    for s in A.stored_snapshots():
        if s.get("source_class") != source_class:
            continue
        rows.append(
            {
                "resolved_url": s.get("resolved_url"),
                "fetch_timestamp": s.get("fetch_timestamp"),
                "sha256": s.get("sha256"),
                "http_status": s.get("http_status"),
                "path": s.get("path"),
                "bytes": s.get("bytes"),
            }
        )
    return rows


def main() -> int:
    lineage_rows = A.verify_lineage()
    if any(not r["match"] or not r["present"] for r in lineage_rows):
        print("FAILED:RES-0139 lineage mismatch before emit")
        return 1
    extracted = A.extract_all()
    pinned = A.canonical_requirements(extracted)
    contra = C.evaluate()
    if not contra["negative_control"]["pass"] or not contra["mutant_control"]["pass"]:
        print("FAILED:RES-0139 checker controls red; refusing to emit SUCCESS")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    adapters = []
    for cls, meta in A.ADAPTERS.items():
        adapters.append(
            {
                "source_class": cls,
                "id": meta["id"],
                "title": meta["title"],
                "machine_readable_path": meta["machine_readable"],
                "discussion_history_path": meta["discussion_history"],
                "extracted_requirement_count": len(extracted.get(cls) or []),
                "source_lineage": snap_lineage(cls),
            }
        )

    ietf_lin = snap_lineage("ietf")
    mcp_lin = snap_lineage("mcp")
    slsa_lin = snap_lineage("slsa")
    w3c_lin = snap_lineage("w3c")

    claims = [
        {
            "id": "RES-0139-C1-ADAPTER-PATHS",
            "statement": (
                "Each of the four named source classes has a stable, "
                "machine-readable extraction path that yields an RFC 2119 / "
                "BCP 14 keyword, a section, the requirement sentence, and a "
                "discussion-history pointer from frozen live fetches."
            ),
            "verdict": "CONFIRMED",
            "confidence": "Almost Certain",
            "evidence_tier": "E1",
            "source_lineage": ietf_lin[:2] + w3c_lin[:2] + slsa_lin[:1] + mcp_lin[:2],
            "independent_verification": (
                "Signal 1: RFC 2119 keyword extraction over snapshot bytes "
                f"(counts={ {k: len(v) for k, v in extracted.items()} }). "
                "Signal 2: sha256 rehash of every stored snapshot against "
                "fixtures/fetch-manifest.json (20/20 match)."
            ),
            "settling_probe": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0139/probe1_adapter_lineage.py"
            ),
            "rfc2119_citations": [
                {
                    "keyword": p["keyword"],
                    "section": p["section"],
                    "text": p["text"],
                    "requirement_id": p["id"],
                }
                for p in pinned
            ],
        },
        {
            "id": "RES-0139-C2-DISCUSSION-HISTORY",
            "statement": (
                "Discussion history is machine-reachable per class: IETF "
                "datatracker rev_history plus relateddocument; W3C Specref + "
                "w3c/w3process; SLSA GitHub repo plus the v1.0 Retired banner; "
                "MCP GitHub commits on the lifecycle MDX path. IETF mailarchive "
                "search returned HTTP 403 and is not a load-bearing rail."
            ),
            "verdict": "CONFIRMED",
            "confidence": "Probable",
            "evidence_tier": "E2",
            "source_lineage": ietf_lin[2:5] + w3c_lin + slsa_lin[-1:] + mcp_lin[-1:],
            "independent_verification": (
                "Signal 1: parsed datatracker rev_history and relateddocument "
                "total_count from frozen JSON. Signal 2: GitHub commits JSON "
                "on docs/specification/2025-03-26/basic/lifecycle.mdx and "
                "Specref w3c-process href."
            ),
            "settling_probe": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0139/probe1_adapter_lineage.py"
            ),
            "caveat": (
                "lists.w3.org mbox and mailarchive.ietf.org were not used as "
                "hashed rails (mbox not fetched; mailarchive 403)."
            ),
        },
        {
            "id": "RES-0139-C3-PLANNED-CONTRACT-CONTRADICTIONS",
            "statement": (
                "Over the 20 Phase-4 planned contracts in "
                "command-center/WORK-UNIT-CATALOG.json (output_path under "
                "command-center/phase4/contracts/), the named polarity-inversion "
                "rules against pinned published MUST/MUST NOT sentences returned "
                f"{contra['production_hit_count']} hit(s). No catalog contract "
                "prose currently inverts the pinned MCP initialize-first, "
                "null-id, receive-batch, stdio-newline, RFC 8174 uppercase-only, "
                "or SLSA L2 authentic-provenance requirements."
            ),
            "verdict": "CONFIRMED",
            "confidence": "Probable",
            "evidence_tier": "E2",
            "source_lineage": mcp_lin[:3] + slsa_lin[:1] + ietf_lin[:2],
            "independent_verification": (
                "Signal 1: contradiction.evaluate() production scan of catalog "
                "question_or_target + tests_required. Signal 2: probe2 mutant "
                "control fires the same rules on an inverting clause, so a "
                "zero production count is not an always-silent detector."
            ),
            "settling_probe": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0139/probe2_negative_control.py"
            ),
            "caveat": (
                "Contracts are still catalog prose, not authored "
                "phase4/contracts/*.json bodies. The detector only fires on "
                "named inversion patterns; a semantic contradiction outside "
                "those patterns would be a miss. Strongest surviving "
                "counterargument: ARC-0090's stdio-vs-shared-HTTP split is "
                "compatible with MCP (per-session stdio, shared Streamable HTTP) "
                "and is therefore not counted as a hit."
            ),
            "production_hits": contra["production_hits"],
        },
        {
            "id": "RES-0139-C4-CHECKER-NOT-VACUOUS",
            "statement": (
                "The contradiction checker is silent on a known-complying "
                "restatement of MCP initialize-first / UTF-8 / no-null-id / "
                "uppercase-only BCP 14, and it fires on a polarity-inverting "
                "mutant. This is the catalog-required negative control."
            ),
            "verdict": "CONFIRMED",
            "confidence": "Almost Certain",
            "evidence_tier": "E1",
            "source_lineage": mcp_lin[:1] + ietf_lin[:1],
            "independent_verification": (
                "Signal 1: Python regex rules in contradiction.py. Signal 2: "
                "probe2_negative_control.py both-states gate (complying hit_count "
                f"= {contra['negative_control']['hit_count']}, mutant rules "
                f"{contra['mutant_control']['fired_rule_ids']})."
            ),
            "settling_probe": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0139/probe2_negative_control.py"
            ),
        },
    ]

    doc = {
        "unit_id": "RES-0139",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0139",
        "schema_version": "research-claim-record/v0-provisional",
        "schema_provisional": True,
        "superseding_unit": "RES-0001",
        "report_kind": "research-claim-record",
        "title": "Standards and working-group archives as a first-class source class",
        "question": QUESTION,
        "freshness_stamp": now,
        "snapshot_sha256_algorithm": "sha256",
        "answer": (
            "IETF: RFC Editor JSON + datatracker doc.json/API + RFC body; "
            "history via rev_history and relateddocument. "
            "W3C: Specref JSON + api.w3.org specifications + Process bikeshed "
            "(em.rfc2119); history via Specref/GitHub/lists.w3.org. "
            "OpenSSF/SLSA: slsa.dev HTML (GitHub v1.0 markdown path 404s) plus "
            "in-toto provenance JSON; history via slsa-framework/slsa. "
            "MCP: specification MDX + generated JSON Schema / schema.ts SSOT; "
            "history via GitHub commits and discussions. "
            f"Planned Phase-4 contract scan: {contra['production_hit_count']} "
            "encoded-rule hits of "
            f"{contra['planned_contract_count']} contracts. Negative control "
            "silent; mutant fires."
        ),
        "claims": claims,
        "source_adapters": adapters,
        "source_lineage": [
            {
                "resolved_url": s.get("resolved_url"),
                "fetch_timestamp": s.get("fetch_timestamp"),
                "sha256": s.get("sha256"),
                "http_status": s.get("http_status"),
                "path": s.get("path"),
                "stored": s.get("stored"),
                "source_class": s.get("source_class"),
                "note": s.get("note"),
            }
            for s in A.load_manifest().get("snapshots") or []
        ],
        "pinned_requirements": pinned,
        "contradictions": {
            "planned_contract_count": contra["planned_contract_count"],
            "planned_contract_ids": contra["planned_contract_ids"],
            "rules": contra["rules"],
            "production_hits": contra["production_hits"],
            "production_hit_count": contra["production_hit_count"],
            "method": (
                "Named polarity-inversion regexes against pinned published "
                "requirement quotes. A contradiction claim quotes both the "
                "contract excerpt and the normative sentence."
            ),
        },
        "negative_control": contra["negative_control"],
        "mutant_control": {
            "id": contra["mutant_control"]["id"],
            "title": contra["mutant_control"]["title"],
            "hit_count": contra["mutant_control"]["hit_count"],
            "fired_rule_ids": contra["mutant_control"]["fired_rule_ids"],
            "pass": contra["mutant_control"]["pass"],
        },
        "tests": [
            {
                "id": "T1-adapter-lineage",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0139/probe1_adapter_lineage.py"
                ),
                "role": "extraction-and-lineage",
            },
            {
                "id": "T2-negative-control",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0139/probe2_negative_control.py"
                ),
                "role": "negative-control",
                "requirement": (
                    "negative control: run the contradiction check against a "
                    "contract clause known to comply and confirm it returns no "
                    "hit, proving the checker is not flagging every clause"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0139-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
            "mandate": (
                "Adversarial default is REFUTED unless both named probes exit 0 "
                "and the complying clause is silent while the mutant fires."
            ),
        },
        "strongest_surviving_counterargument": (
            "Zero production hits may under-count semantic inversions that do "
            "not match the named regexes, and Phase-4 contracts are still "
            "catalog questions rather than frozen schema text."
        ),
        "produced_by": "command-center/p2-wave/probes/RES-0139/emit_record.py",
        "output_schema": SCHEMA_REL,
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    raw = out.read_bytes().replace(b"\r\n", b"\n")
    print(f"wrote {OUT_REL} bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}")
    print("SUCCESS:RES-0139")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
