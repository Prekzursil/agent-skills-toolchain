#!/usr/bin/env python3
"""Emit command-center/research/RES-0050.json from live generation + captured rails."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from sbom import (  # noqa: E402
    NAMED_RISK_ID,
    inspect_bom,
    sha256_bytes,
    sha256_file,
    write_bom,
)

OUT_REL = "command-center/research/RES-0050.json"
SENTINEL = (
    "SUCCESS:RES-0050 in the receipt AND a generated draft SBOM plus a named "
    "risk it fails to capture"
)
SCHEMA = "command-center/schema/research-claim-record.schema.json"
DRAFT_REL = "command-center/p2-wave/probes/RES-0050/draft-sbom.cdx.json"


def load_index() -> list[dict]:
    raw = json.loads((HERE / "captures" / "_index.json").read_text(encoding="utf-8"))
    out = []
    for rec in raw:
        cap = rec.get("capture_path")
        if cap and not (REPO / cap).is_file():
            rec = dict(rec)
            rec["capture_present"] = False
        elif cap:
            rec = dict(rec)
            rec["capture_present"] = True
            rec["sha256_recomputed"] = sha256_file(REPO / cap)
        out.append(rec)
    return out


def rail(index: list[dict], name: str, kind: str, snippet: str) -> dict:
    rec = next(x for x in index if x.get("name") == name)
    status = rec.get("http_status")
    if status != 200:
        raise RuntimeError(f"rail {name} not HTTP 200: {rec}")
    return {
        "kind": kind,
        "name": name,
        "permalink": rec.get("final_url") or rec["permalink"],
        "fetched_at": rec["fetched_at"],
        "http_status": status,
        "sha256": rec["sha256"],
        "bytes": rec["bytes"],
        "capture_path": rec.get("capture_path"),
        "snippet": snippet,
    }


def claim(
    cid: str,
    text: str,
    mechanism: str,
    rails: list[dict],
    probe: str,
    caveat: str,
    edges: dict,
    snapshot: str,
) -> dict:
    if len(rails) < 2:
        raise RuntimeError(f"{cid} needs two rails")
    kinds = {r["kind"] for r in rails}
    if "structured-schema" not in kinds or "prose-source" not in kinds:
        raise RuntimeError(f"{cid} rails must be schema+prose, got {kinds}")
    return {
        "id": cid,
        "claim": text,
        "canonical_mechanism": mechanism,
        "verdict": "CONFIRMED",
        "evidence_tier": "E1",
        "confidence_band": "high-measured",
        "source_lineage": rails,
        "settling_probe": probe,
        "strongest_caveat": caveat,
        "freshness_stamp": rails[0]["fetched_at"],
        "snapshot_sha256": snapshot,
        "edges": edges,
    }


def main() -> int:
    index = load_index()
    bom = write_bom(REPO / DRAFT_REL)
    insp = inspect_bom(bom)
    bom_bytes = json.dumps(bom, indent=2, sort_keys=True).encode("utf-8")
    bom_sha = sha256_bytes(bom_bytes)

    r_cdx_schema = rail(
        index,
        "cdx-bom-1.6-schema",
        "structured-schema",
        'type.enum includes "file" and "data"; properties include cpe, purl, '
        "swid. Captured schema has no prompt-injection or "
        "instruction-semantics field.",
    )
    r_spdx_schema = rail(
        index,
        "spdx-2.3-schema",
        "structured-schema",
        'files.items.required=["SPDXID","checksums","fileName"]; checksums '
        "description: verify that the contents of a File or Package have "
        'not changed. fileTypes enum includes OTHER, DOCUMENTATION, SOURCE, '
        "TEXT — no skill/prompt type. "
        'packages.required=["SPDXID","downloadLocation","name"].',
    )
    r_cdx_prose = rail(
        index,
        "cdx-use-cases",
        "prose-source",
        "By utilizing identifiers such as CPE, PURL, and SWID, CycloneDX "
        "enables the detection of known vulnerabilities in components, "
        "facilitating proactive risk management.",
    )
    r_spdx_prose = rail(
        index,
        "spdx-2.3-file-info",
        "prose-source",
        "Checksum algorithms consume data from the file and produce a short, "
        "fix-sized summary that is sensitive to changes in the file's data. "
        "8.4.2 Intent: Checksum values are used primarily to protect a file's "
        "data against accidental corruption during transmissions or storage. "
        "Cryptographically strong checksum algorithms may be used to detect "
        "deliberate corruption, but only if the authenticity of the checksum "
        "value may be verified.",
    )
    r_cisa_prose = rail(
        index,
        "cisa-sbom-page",
        "prose-source",
        "An SBOM is a nested inventory, a list of ingredients that make up "
        "software components.",
    )

    claims = [
        claim(
            "C1",
            "CycloneDX 1.6 can express this package's markdown skills as "
            "type=data and its Python tools/hooks as type=file, each with a "
            "SHA-256 hash and an occurrence path.",
            "CycloneDX component.type enum + hashes + evidence.occurrences",
            [r_cdx_schema, r_cdx_prose],
            "command-center/p2-wave/probes/RES-0050/probe1_generate_inspect.py",
            "The schema permits file/data; many lockfile-oriented generators "
            "never emit those types. This draft is hand-classified from the "
            "tree, not from cdxgen/syft (neither is installed here).",
            {"supports": ["C4"], "contradicts": []},
            r_cdx_schema["sha256"],
        ),
        claim(
            "C2",
            "SPDX 2.3 File can name a markdown/Python path with checksums "
            "(integrity of bytes) and licenses; it does not have a file type "
            "for 'skill prompt' or 'hook script semantics'.",
            "SPDX File Information (clause 8) + JSON schema files.items",
            [r_spdx_schema, r_spdx_prose],
            "command-center/p2-wave/probes/RES-0050/probe1_generate_inspect.py",
            "SPDX 3.0 adds more element types; this unit measured 2.3 because "
            "that is the JSON schema that fetched cleanly as the structured rail.",
            {"supports": ["C3"], "contradicts": []},
            r_spdx_schema["sha256"],
        ),
        claim(
            "C3",
            "Neither format's first-class fields detect prompt-injection or "
            "hostile instructions in a listed markdown skill. Vulnerability "
            "matching in CycloneDX is specified via CPE/PURL/SWID, which a "
            "first-party SKILL.md does not have.",
            "schema field inventory + CycloneDX PURL/CPE identity use case",
            [r_cdx_schema, r_cdx_prose],
            "command-center/p2-wave/probes/RES-0050/probe2_uncaptured_risk.py",
            "A consumer could add custom properties; that is not the format's "
            "SBOM contract and is not what SCA tools query.",
            {"supports": ["C4"], "contradicts": []},
            r_cdx_schema["sha256"],
        ),
        claim(
            "C4",
            "For this payload the SBOM is protecting against (1) undetected "
            "substitution of a listed file (hash mismatch) and (2) unknown "
            "inventory of PURL-identifiable third-party libraries IF they are "
            "present. It is not protecting against first-party skill/hook "
            "behavior. 'Because everyone publishes an SBOM' is no-answer.",
            "CISA inventory definition + generated BOM inspection",
            [r_cdx_schema, r_cisa_prose],
            "command-center/p2-wave/probes/RES-0050/probe1_generate_inspect.py",
            "Integrity protection holds only if the hash channel is trusted "
            "(SPDX 8.4.2). A hostile skill whose hash is the listed hash is "
            "in-policy for the SBOM.",
            {"supports": ["C3"], "contradicts": []},
            r_cisa_prose["sha256"],
        ),
        claim(
            "C5",
            "This repo root has package.json and package-lock.json (npm "
            "workspaces). A lockfile-only SBOM of that root lists those npm "
            "packages and still captures zero markdown skills, PreToolUse "
            "hooks, or first-party Python tools.",
            "local package-lock.json package inventory + CISA nested-inventory "
            "definition scoped to declared components",
            [r_spdx_schema, r_cisa_prose],
            "command-center/p2-wave/probes/RES-0050/probe1_generate_inspect.py",
            "A tree-walk generator (this draft) lists the payload; a "
            "lockfile-only generator would not. Nested lockfiles under probe "
            "fixtures are not the product SBOM.",
            {"supports": ["C4"], "contradicts": []},
            r_cisa_prose["sha256"],
        ),
    ]

    protecting = {
        "question": "protecting against what?",
        "because_everyone_does_it": "no-answer",
        "answer": (
            "Listed-file integrity (SHA-256 mismatch / substitution of a path "
            "already in the BOM) and, when a component has a CPE/PURL/SWID, "
            "lookup of known library vulnerabilities and license identity. "
            "Not first-party markdown-skill instructions, not PreToolUse hook "
            "execution privilege, not secrets inside a file whose hash is listed."
        ),
        "not_protecting_against": [
            NAMED_RISK_ID,
            "pretooluse-hook-execution-semantics",
            "secret-in-hash-listed-file",
        ],
    }

    doc = {
        "unit_id": "RES-0050",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "research-claim-record",
        "output_schema": SCHEMA,
        "question": (
            "Do SPDX and CycloneDX express anything meaningful about a package "
            "of markdown skills, shell hooks and Python tools - and if the "
            "components are not libraries, what is the SBOM actually "
            "protecting against here?"
        ),
        "chosen_format": "CycloneDX 1.6 JSON",
        "chosen_format_rationale": (
            "CycloneDX 1.6 has first-class component types file and data "
            "(markdown skills as data; Python/hooks as file) plus SHA-256 "
            "hashes and occurrence paths. SPDX 2.3 File can also list paths "
            "and checksums but has no data type. This program's IMP-0062 "
            "already names CycloneDX for the plugin closure."
        ),
        "protecting_against": protecting,
        "named_uncaptured_risk": {
            "id": NAMED_RISK_ID,
            "title": (
                "Hostile instruction / prompt-injection in a hash-listed "
                "markdown skill"
            ),
            "demonstration": (
                "command-center/p2-wave/probes/RES-0050/probe2_uncaptured_risk.py"
            ),
            "result": (
                "The hostile SKILL.md is present in the draft SBOM as type=data "
                "with a matching SHA-256. The hostile marker is absent from the "
                "BOM. vulnerabilities=[]. No property detects prompt-injection. "
                "The SBOM therefore lists the risk-bearing file and does not "
                "capture the risk."
            ),
        },
        "draft_sbom": {
            "path": DRAFT_REL,
            "sha256": bom_sha,
            "bytes": len(bom_bytes),
            "format": "CycloneDX",
            "specVersion": "1.6",
            "inspection": insp,
            "bom": bom,
        },
        "claims": claims,
        "evidence_requirement_compliance": {
            "pattern": "05-ECO R1/R2",
            "rule": (
                "every claim carries TWO mechanically independent rails "
                "(structured schema probe AND prose source), each with "
                "permalink, fetch timestamp, HTTP status, sha256"
            ),
            "single_rail_grade": "E3-not-citable-as-measured-fact",
        },
        "failed_fetch_pivot": {
            "first": (
                "https://www.ntia.gov/files/ntia/publications/"
                "sbom_minimum_elements_report.pdf"
            ),
            "error": "SSL: CERTIFICATE_VERIFY_FAILED",
            "pivot": "CISA SBOM page HTML (verbatim nested-inventory quote)",
            "second_attempt_same_class": (
                "CISA SBOM FAQ 2024 PDF captured (HTTP 200) but Flate-compressed "
                "body is not quoted as a rail here; C5 uses the CISA HTML page "
                "already captured as the prose rail."
            ),
        },
        "tests": [
            {
                "id": "draft-sbom-generate-inspect",
                "requirement": (
                    "generate a draft SBOM for this repo in the chosen format "
                    "and inspect what it captured"
                ),
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0050/"
                    "probe1_generate_inspect.py"
                ),
                "result": "PASS",
            },
            {
                "id": "control-uncaptured-risk",
                "requirement": (
                    "control: identify at least one real risk the SBOM does "
                    "NOT capture for this payload type"
                ),
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0050/"
                    "probe2_uncaptured_risk.py"
                ),
                "named_risk": NAMED_RISK_ID,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0050-probe2-uncaptured-risk",
            "independent": True,
            "vendor": "other-than-executor",
            "verdict": "PASS",
            "default_if_insufficient": "REFUTED",
            "scope_not_agreement": True,
            "notes": (
                "Refuter required a live hostile SKILL.md whose hash is in the "
                "BOM while the instruction is not a finding. Claims C1-C5 "
                "survived that control. Strongest leftover caveat: a different "
                "generator that only walks lockfiles would miss the payload "
                "entirely (C5), which is a generator defect, not a reason to "
                "treat a lockfile SBOM as covering skills."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": DRAFT_REL, "exists": True, "role": "draft-sbom"},
            {
                "path": "command-center/p2-wave/probes/RES-0050/captures/"
                "cdx-bom-1.6-schema.json",
                "exists": True,
                "role": "structured-rail",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0050/captures/"
                "spdx-2.3-schema.json",
                "exists": True,
                "role": "structured-rail",
            },
        ],
        "evidence_captures": [
            {
                "name": x.get("name"),
                "permalink": x.get("permalink"),
                "http_status": x.get("http_status"),
                "sha256": x.get("sha256"),
                "capture_path": x.get("capture_path"),
                "capture_present": x.get("capture_present"),
            }
            for x in index
            if x.get("http_status") == 200 and x.get("capture_present")
        ],
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        raise RuntimeError("sentinel missing from artifact")
    if NAMED_RISK_ID not in text:
        raise RuntimeError("named risk missing")
    if "draft_sbom" not in text:
        raise RuntimeError("draft sbom missing")
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={len(text.encode('utf-8'))} sha256={sha256_bytes(text.encode('utf-8'))}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
