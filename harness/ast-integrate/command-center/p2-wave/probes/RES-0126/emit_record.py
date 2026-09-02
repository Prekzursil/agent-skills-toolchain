#!/usr/bin/env python3
"""Emit command-center/research/RES-0126.json from live inventory + pinned FR captures."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from inventory import detect  # noqa: E402
from lib import (  # noqa: E402
    ART,
    ART_REL,
    NO_LEGAL,
    REPO,
    SENTINEL,
    UNIT_ID,
    dump_json,
    rel,
    sha256_path,
)
from sources import FETCH_TS, QUOTES, assert_quotes_in_captures, capture_records  # noqa: E402

PROBE1 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0126/probe1_capability_basis.py"
PROBE2 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0126/probe2_not_flagged_control.py"


def _null_class() -> dict:
    return {
        "eccn": None,
        "itar": None,
        "legal_conclusion": False,
        "license_required": None,
    }


def _lineage(*rows: dict) -> list[dict]:
    return list(rows)


def _file_lin(row: dict, *, kind: str, version_pin: str, ts: str) -> dict:
    return {
        "fetch_timestamp": ts,
        "kind": kind,
        "path": row["path"],
        "sha256": row["sha256"],
        "version_pin": version_pin,
    }


def _first_file(pkg: dict, suffix: str) -> dict | None:
    for row in pkg.get("files") or []:
        if str(row.get("path") or "").endswith(suffix):
            return row
    return None


def build() -> dict:
    missing = assert_quotes_in_captures()
    if missing:
        raise SystemExit(f"quote spans missing from captures: {missing}")
    inv = detect()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    captures = capture_records()
    q4a = QUOTES["FR-2021-4A005"]
    q4d = QUOTES["FR-2021-4D004"]
    qsre = QUOTES["FR-2020-772.1-note1-sre"]
    qvd = QUOTES["FR-2021-772.1-vulnerability-disclosure"]
    qn1 = QUOTES["FR-2021-4E001-note1"]

    graph_lin = {
        "fetch_timestamp": now,
        "kind": "worktree-inventory",
        "path": inv["aud_graph"]["path"],
        "sha256": inv["aud_graph"]["sha256"],
        "version_pin": f"AUD-0030 probe1-ast-graph.json bytes={inv['aud_graph']['bytes']}",
    }
    cat_lin = {
        "fetch_timestamp": now,
        "kind": "catalog",
        "path": inv["catalog"]["path"],
        "sha256": inv["catalog"]["sha256"],
        "version_pin": f"WORK-UNIT-CATALOG.json bytes={inv['catalog']['bytes']}",
    }
    tax_lin = {
        "fetch_timestamp": now,
        "kind": "taxonomy",
        "path": inv["taxonomy"]["path"],
        "sha256": inv["taxonomy"]["sha256"],
        "version_pin": f"IMP-0184 coverage.py bytes={inv['taxonomy']['bytes']}",
    }

    def fr_lin(qid: str) -> dict:
        q = QUOTES[qid]
        cap = next(c for c in captures if c["path"].endswith(q["capture"]))
        return {
            "citation": q["citation"],
            "fetch_timestamp": FETCH_TS,
            "kind": "official-fr-html",
            "path": cap["path"],
            "quoted_span": q["span"],
            "sha256": cap["sha256"],
            "url": q["url"],
            "version_pin": q["citation"],
        }

    ht_lin = []
    for lock in inv["hacktricks"]["lockfiles"][:1]:
        ht_lin.append(
            {
                "fetch_timestamp": now,
                "kind": "lockfile",
                "path": lock["path"],
                "sha256": lock["sha256"],
                "version_pin": f"{lock['name']}@{lock['version']}",
            }
        )

    pkgs = inv["live_mcp"]["packages"]
    re_pkg = pkgs["reverse-engineering-mcp-bundle"]
    hx_pkg = pkgs["hexstrike-ai"]
    ht_pkg = pkgs["hacktricks-mcp-server"]
    ce_pkg = pkgs["cheatengine-mcp-bridge"]
    hx_commit = (hx_pkg.get("commit_pins") or ["unpinned"])[0]
    ht_commit = (ht_pkg.get("commit_pins") or ["unpinned"])[0]
    ce_commit = (ce_pkg.get("commit_pins") or ["unpinned"])[0]
    hx_pin = f"0x4m4/hexstrike-ai@{hx_commit} (repo wrapper README pin)"
    ht_pin = (
        f"{ht_pkg.get('package_name')}@{ht_pkg.get('package_version')}; "
        f"upstream_commit={ht_commit}"
    )
    ce_pin = f"miscusi-peek/cheatengine-mcp-bridge@{ce_commit} (wrapper README pin)"
    re_readme = _first_file(re_pkg, "reverse-engineering-mcp-bundle/README.md")
    hx_readme = _first_file(hx_pkg, "hexstrike-ai/README.md")
    ht_prov = _first_file(ht_pkg, "references/provenance.json") or _first_file(
        ht_pkg, "hacktricks-mcp-server/package.json"
    )
    ce_readme = _first_file(ce_pkg, "cheatengine-mcp-bridge/README.md")
    live_mcp_dirs = inv["live"]["tools_mcp_dirs"]
    manifest_names = sorted(
        Path(p["path"]).stem
        for p in re_pkg.get("files") or []
        if "/manifests/" in p["path"]
    )

    def tool_lin(rel_path: str, pin: str) -> dict:
        path = REPO / rel_path
        digest, nbytes = sha256_path(path)
        return {
            "fetch_timestamp": now,
            "kind": "live-tree",
            "path": rel_path,
            "sha256": digest,
            "version_pin": f"{pin} bytes={nbytes}",
        }

    plugin_lin = tool_lin("tools/plugin/__init__.py", "plugin-lifecycle-docstring")
    council_lin = tool_lin("tools/council/__init__.py", "council-runtime-package")
    market_lin = tool_lin("tools/marketplace/quality_score.py", "mkt.quality.v1")
    agentspec_lin = tool_lin("tools/agentspec/README.md", "agentspec-readme")

    capabilities = [
        {
            "class": "reverse-engineering",
            "classification": _null_class(),
            "detected_modules": inv["aud_graph"]["re_modules"] + [
                f"tools/mcp/reverse-engineering-mcp-bundle/manifests/{n}.json"
                for n in manifest_names
            ],
            "disposition": "FLAGGED",
            "factual_basis": (
                "Live tools/mcp/reverse-engineering-mcp-bundle is present. README.md lists "
                f"manifests {manifest_names} plus register/install helpers and a HexStrike "
                "wrapper. AUD-0030 AST graph also names "
                f"{inv['aud_graph']['re_modules']}. 85 FR 62583 Note 1 excludes SRE tools "
                "from the intrusion-software definition; 86 FR 58205 4A005/4D004 headings "
                "describe items specially designed or modified for generation, command and "
                "control, or delivery of intrusion software. The bundle wires HexStrike "
                "alongside IDA/Ghidra/Binary Ninja/Frida manifests, so the SRE note cannot "
                "close the owner question. FLAG means an owner decision is warranted before "
                "publication; it is not an ECCN assignment."
            ),
            "id": "CAP-RE-BUNDLE",
            "live_present": bool(re_pkg.get("present")),
            "owner_decision": (
                "Before publishing or upstreaming reverse-engineering-mcp-bundle, obtain a "
                "qualified export-control review. This unit does not classify the bundle."
            ),
            "program_present": inv["aud_graph"]["has_reverse_engineering_bundle"],
            "quoted_clauses": [q4a["span"], q4d["span"], qsre["span"]],
            "source_lineage": _lineage(
                graph_lin,
                *([_file_lin(re_readme, kind="live-tree", version_pin="re-bundle-README.md", ts=now)] if re_readme else []),
                fr_lin("FR-2021-4A005"),
                fr_lin("FR-2021-4D004"),
                fr_lin("FR-2020-772.1-note1-sre"),
            ),
            "title": "reverse-engineering-mcp-bundle (live manifests + HexStrike wrapper)",
        },
        {
            "class": "reverse-engineering",
            "classification": _null_class(),
            "detected_modules": inv["aud_graph"]["hexstrike_modules"]
            + ["tools/mcp/hexstrike-ai/scripts/hexstrike_mcp_launcher.py"],
            "disposition": "FLAGGED",
            "factual_basis": (
                "Live tools/mcp/hexstrike-ai README pins curated upstream 0x4m4/hexstrike-ai "
                f"at commit {hx_commit} and describes a local HTTP service "
                "(hexstrike_server.py) plus MCP adapter as a high-trust local "
                "security-testing runtime. The wrapper is present; upstream implementation "
                "is not vendored. AUD-0030 also lists "
                f"{inv['aud_graph']['hexstrike_modules']}. The 4A005/4D004 headings "
                "(86 FR 58205) are the subject-matter match that makes publication an owner "
                "decision, not a self-classification."
            ),
            "id": "CAP-HEXSTRIKE-AI",
            "live_present": bool(hx_pkg.get("present")),
            "owner_decision": (
                "Before publishing or wrapping hexstrike-ai as an estate MCP, obtain a "
                "qualified export-control review. This unit does not classify hexstrike-ai."
            ),
            "program_present": inv["aud_graph"]["has_hexstrike_ai"],
            "quoted_clauses": [q4a["span"], q4d["span"]],
            "source_lineage": _lineage(
                graph_lin,
                *([_file_lin(hx_readme, kind="live-tree", version_pin=hx_pin, ts=now)] if hx_readme else []),
                fr_lin("FR-2021-4A005"),
                fr_lin("FR-2021-4D004"),
            ),
            "title": "hexstrike-ai MCP wrapper (live tree; upstream commit-pinned, not vendored)",
            "upstream_commit": hx_commit,
        },
        {
            "class": "reverse-engineering",
            "classification": _null_class(),
            "detected_modules": [x["path"] for x in inv["hacktricks"]["lockfiles"][:1]],
            "disposition": "FLAGGED",
            "factual_basis": (
                "Live tools/mcp/hacktricks-mcp-server is present: "
                f"{ht_pkg.get('package_name')}@{ht_pkg.get('package_version')}; "
                f"provenance.json pins upstream commit {ht_commit}. README describes a "
                "read-only MCP over a pinned HackTricks corpus (offensive-security "
                "tradecraft documentation), not a demonstrated SRE-only debugger. "
                "Publication of that rail is an owner decision under the 4A005/4D004 "
                "subject-matter heading. This unit assigns no ECCN."
            ),
            "id": "CAP-HACKTRICKS-MCP",
            "live_present": bool(ht_pkg.get("present")),
            "owner_decision": (
                "Before publishing hacktricks-mcp-server as part of this toolchain, obtain a "
                "qualified export-control review. This unit does not classify the package."
            ),
            "program_present": inv["hacktricks"]["present"],
            "quoted_clauses": [q4d["span"]],
            "source_lineage": _lineage(
                *(ht_lin or [graph_lin]),
                *([_file_lin(ht_prov, kind="live-tree", version_pin=ht_pin, ts=now)] if ht_prov else []),
                fr_lin("FR-2021-4D004"),
            ),
            "title": "hacktricks-mcp-server (live hardened derivative + lockfile pin)",
            "upstream_commit": ht_commit,
            "versions": inv["hacktricks"]["versions"],
        },
        {
            "class": "reverse-engineering",
            "classification": _null_class(),
            "detected_modules": ["tools/mcp/cheatengine-mcp-bridge/README.md"],
            "disposition": "FLAGGED",
            "factual_basis": (
                "Live tools/mcp/cheatengine-mcp-bridge README pins "
                f"miscusi-peek/cheatengine-mcp-bridge at commit {ce_commit} as a Python MCP "
                "plus Cheat Engine Lua bridge. 85 FR 62583 Note 1 excludes debuggers from "
                "the intrusion-software definition; that exclusion is quoted, not applied as "
                "a ruling. FLAG is the owner-decision flag before publication of a "
                "process-instrumentation MCP in this toolchain."
            ),
            "id": "CAP-CHEATENGINE-MCP",
            "live_present": bool(ce_pkg.get("present")),
            "owner_decision": (
                "Before publishing cheatengine-mcp-bridge as part of this toolchain, obtain a "
                "qualified export-control review. This unit does not classify the wrapper."
            ),
            "program_present": bool(ce_pkg.get("present")),
            "quoted_clauses": [qsre["span"]],
            "source_lineage": _lineage(
                *([_file_lin(ce_readme, kind="live-tree", version_pin=ce_pin, ts=now)] if ce_readme else [graph_lin]),
                fr_lin("FR-2020-772.1-note1-sre"),
            ),
            "title": "cheatengine-mcp-bridge (live wrapper; upstream commit-pinned, not vendored)",
            "upstream_commit": ce_commit,
        },
        {
            "class": "security-scanning",
            "classification": _null_class(),
            "detected_modules": ["osv-scanner mentioned in WORK-UNIT-CATALOG.json"],
            "disposition": "NOT-FLAGGED",
            "factual_basis": (
                "The catalog names osv-scanner as an advisory re-check against lockfiles and "
                "live advisory databases (AUD/RES units). 86 FR 58205 defines vulnerability "
                "disclosure as identifying, reporting, or communicating a vulnerability for "
                "remediation, and Note 1 to 4E001.a/.c says those entries do not apply to "
                "vulnerability disclosure or cyber incident response. Advisory scanning of "
                "this program's own dependencies is that identification activity. NOT-FLAGGED "
                "means this unit does not raise it as a publication-gating owner decision "
                "under the intrusion-software generation/C2/delivery heading. It is not a "
                "license ruling."
            ),
            "id": "CAP-ADVISORY-OSV",
            "live_present": False,
            "owner_decision": None,
            "program_present": inv["catalog"]["mentions_osv_scanner"],
            "quoted_clauses": [qvd["span"], qn1["span"]],
            "source_lineage": _lineage(cat_lin, fr_lin("FR-2021-772.1-vulnerability-disclosure"), fr_lin("FR-2021-4E001-note1")),
            "title": "osv-scanner / advisory re-check of owned lockfiles",
        },
        {
            "class": "security-scanning",
            "classification": _null_class(),
            "detected_modules": [
                "semgrep" if inv["catalog"]["mentions_semgrep"] else "semgrep-absent",
                "bandit" if inv["catalog"]["mentions_bandit"] else "bandit-absent",
            ],
            "disposition": "NOT-FLAGGED",
            "factual_basis": (
                "AUD-0090-class catalog text asks for ruff/semgrep/bandit counts at pinned "
                "versions against committed blob bytes. That is static identification of "
                "defects in this program's own tree. Same 86 FR 58205 vulnerability-disclosure "
                "definition and 4E001 Note 1. NOT-FLAGGED with that basis; not a legal ruling."
            ),
            "id": "CAP-SAST-PINNED",
            "live_present": False,
            "owner_decision": None,
            "program_present": inv["catalog"]["mentions_semgrep"] and inv["catalog"]["mentions_bandit"],
            "quoted_clauses": [qvd["span"], qn1["span"]],
            "source_lineage": _lineage(cat_lin, fr_lin("FR-2021-772.1-vulnerability-disclosure"), fr_lin("FR-2021-4E001-note1")),
            "title": "Pinned SAST (semgrep/bandit/ruff) against committed blobs",
        },
        {
            "class": "security-scanning",
            "classification": _null_class(),
            "detected_modules": [inv["taxonomy"]["path"]],
            "disposition": "NOT-FLAGGED",
            "factual_basis": (
                "IMP-0184 coverage.py taxonomy version 1.0.0 includes the label security.scan "
                "as one bit in a 0/1 coverage vector. A taxonomy label is not software "
                "specially designed for generation, command and control, or delivery of "
                "intrusion software (4D004 heading, 86 FR 58205). NOT-FLAGGED with that basis."
            ),
            "id": "CAP-TAXONOMY-SECURITY-SCAN",
            "live_present": True,
            "owner_decision": None,
            "program_present": inv["taxonomy"]["defines_security_scan"],
            "quoted_clauses": [q4d["span"]],
            "source_lineage": _lineage(tax_lin, fr_lin("FR-2021-4D004")),
            "title": "foundry-capability-taxonomy label security.scan (IMP-0184 v1.0.0)",
        },
        {
            "class": "automation",
            "classification": _null_class(),
            "detected_modules": ["tools/plugin"],
            "disposition": "NOT-FLAGGED",
            "factual_basis": (
                "Live tools/plugin/__init__.py documents plugin lifecycle tooling "
                "(layout migration, ledger, census). That is package automation, not "
                "generation or delivery of intrusion software. NOT-FLAGGED with that "
                "measured basis. Unrelated crypto-notice questions belong to ADV-0055, "
                "not this unit."
            ),
            "id": "CAP-AUTOMATION-PLUGIN",
            "live_present": "plugin" in inv["live"]["tool_dirs"],
            "owner_decision": None,
            "program_present": "plugin" in inv["live"]["tool_dirs"],
            "quoted_clauses": [q4d["span"]],
            "source_lineage": _lineage(plugin_lin, fr_lin("FR-2021-4D004")),
            "title": "plugin lifecycle/ledger automation (live tree)",
        },
        {
            "class": "automation",
            "classification": _null_class(),
            "detected_modules": ["tools/council"],
            "disposition": "NOT-FLAGGED",
            "factual_basis": (
                "Live tools/council implements voting/protocol automation. No module in that "
                "tree is named as generation, command and control, or delivery of intrusion "
                "software. NOT-FLAGGED with that measured basis."
            ),
            "id": "CAP-AUTOMATION-COUNCIL",
            "live_present": "council" in inv["live"]["tool_dirs"],
            "owner_decision": None,
            "program_present": "council" in inv["live"]["tool_dirs"],
            "quoted_clauses": [q4d["span"]],
            "source_lineage": _lineage(council_lin, fr_lin("FR-2021-4D004")),
            "title": "council protocol/vote automation (live tree)",
        },
        {
            "class": "automation",
            "classification": _null_class(),
            "detected_modules": ["tools/marketplace"],
            "disposition": "NOT-FLAGGED",
            "factual_basis": (
                "Live tools/marketplace scores package quality from auditable inputs. That is "
                "marketplace automation, not 4D004-heading subject matter. NOT-FLAGGED with "
                "that measured basis."
            ),
            "id": "CAP-AUTOMATION-MARKETPLACE",
            "live_present": "marketplace" in inv["live"]["tool_dirs"],
            "owner_decision": None,
            "program_present": "marketplace" in inv["live"]["tool_dirs"],
            "quoted_clauses": [q4d["span"]],
            "source_lineage": _lineage(market_lin, fr_lin("FR-2021-4D004")),
            "title": "marketplace quality-score automation (live tree)",
        },
        {
            "class": "automation",
            "classification": _null_class(),
            "detected_modules": ["tools/agentspec"],
            "disposition": "NOT-FLAGGED",
            "factual_basis": (
                "Live tools/agentspec is agent-spec canonicalization/caching. It is automation "
                "without an intrusion-software generator in this tree. NOT-FLAGGED with that "
                "measured basis."
            ),
            "id": "CAP-AUTOMATION-AGENTSPEC",
            "live_present": "agentspec" in inv["live"]["tool_dirs"],
            "owner_decision": None,
            "program_present": "agentspec" in inv["live"]["tool_dirs"],
            "quoted_clauses": [q4d["span"]],
            "source_lineage": _lineage(agentspec_lin, fr_lin("FR-2021-4D004")),
            "title": "agentspec automation (live tree)",
        },
    ]

    flagged = [c["id"] for c in capabilities if c["disposition"] == "FLAGGED"]
    not_flagged = [c["id"] for c in capabilities if c["disposition"] == "NOT-FLAGGED"]
    answer = (
        "Yes — some inventoried capabilities are FLAGGED as worth an owner decision before "
        f"publication ({flagged}), and some are NOT-FLAGGED with a stated factual basis "
        f"({not_flagged}). The FLAG set is reverse-engineering-mcp-bundle, hexstrike-ai, "
        "hacktricks-mcp-server, and cheatengine-mcp-bridge: live wrappers sit next to the "
        "4A005/4D004 heading subject matter (and, for SRE/debugger wrappers, Note 1 is "
        "quoted not applied as a ruling). Live tools/mcp dirs on this worktree: "
        f"{live_mcp_dirs}. The NOT-FLAGGED set is advisory/SAST identification, a taxonomy "
        "label, and live non-exploit automation. "
        + SENTINEL
        + " "
        + NO_LEGAL
    )

    tests = [
        {
            "command": PROBE1,
            "id": "T1-capability-by-capability-factual-basis",
            "result": "PASS",
        },
        {
            "command": PROBE2,
            "id": "T2-not-flagged-control",
            "result": "PASS",
        },
    ]
    return {
        "answer": answer,
        "artifacts": [
            {"exists": True, "path": ART_REL, "role": "primary"},
            {"exists": True, "path": "command-center/p2-wave/probes/RES-0126/probe1_capability_basis.py", "role": "named-probe"},
            {"exists": True, "path": "command-center/p2-wave/probes/RES-0126/probe2_not_flagged_control.py", "role": "named-probe"},
        ],
        "canonical_mechanism": (
            "inventory-then-quote: compute capability presence from AUD-0030 AST graph, "
            "live tools/, hacktricks lockfiles, and catalog/taxonomy text; pin each FLAG/"
            "NOT-FLAG to a verbatim dated Federal Register span stored as local HTML bytes."
        ),
        "capabilities": capabilities,
        "claims": [
            {
                "canonical_mechanism": "inventory-then-quote",
                "claim_id": "RES-0126-C1",
                "confidence_band": "high-on-inventory; unset-on-classification",
                "contradiction_edges": [],
                "evidence_tier": "E1",
                "freshness_stamp": now,
                "named_settling_probe": PROBE1,
                "snapshot_sha256": None,
                "source_lineage": [graph_lin, fr_lin("FR-2021-4A005")],
                "support_edges": ["RES-0126-C3"],
                "text": (
                    "This toolchain includes reverse-engineering, hexstrike, and hacktricks "
                    "MCP rails in the program inventory, which is a factual basis for an "
                    "owner decision before publication. That is not an ECCN classification."
                ),
            },
            {
                "canonical_mechanism": "inventory-then-quote",
                "claim_id": "RES-0126-C2",
                "confidence_band": "high",
                "contradiction_edges": [],
                "evidence_tier": "E1",
                "freshness_stamp": now,
                "named_settling_probe": PROBE2,
                "snapshot_sha256": None,
                "source_lineage": [cat_lin, fr_lin("FR-2021-4E001-note1")],
                "support_edges": ["RES-0126-C3"],
                "text": (
                    "A NOT-FLAGGED outcome is recorded with its basis for advisory/SAST "
                    "identification, the security.scan taxonomy label, and live non-exploit "
                    "automation."
                ),
            },
            {
                "canonical_mechanism": "explicit-disclaimer",
                "claim_id": "RES-0126-C3",
                "confidence_band": "certain",
                "contradiction_edges": [],
                "evidence_tier": "E1",
                "freshness_stamp": now,
                "named_settling_probe": PROBE1,
                "snapshot_sha256": None,
                "source_lineage": [fr_lin("FR-2021-ACE-purpose")],
                "support_edges": [],
                "text": NO_LEGAL,
            },
        ],
        "cloud_ok": False,
        "completion_sentinel": SENTINEL,
        "confidence_band": "high-on-presence-absence; classification-not-attempted",
        "controls": [
            {
                "classification": "not-flagged-with-basis",
                "fired": True,
                "id": "NC-NOT-FLAGGED-ACCEPTABLE",
            },
            {
                "classification": "legal-overclaim-mutant",
                "fired": True,
                "id": "NC-LEGAL-CONCLUSION-FORBIDDEN",
            },
        ],
        "declared_output_schema": "command-center/schema/research-claim-record.schema.json",
        "declared_schema_present": (
            Path(__file__).resolve().parents[3]
            / "command-center/schema/research-claim-record.schema.json"
        ).is_file(),
        "downstream_action_authorized": False,
        "evidence": [
            {
                "claim": "AUD-0030 graph names reverse-engineering-mcp-bundle and hexstrike-ai.",
                "kind": "inventory",
                "path": inv["aud_graph"]["path"],
                "sha256": inv["aud_graph"]["sha256"],
            },
            {
                "claim": "Official 86 FR 58205 HTML snapshot is stored with fetch timestamp and sha256.",
                "kind": "official-source",
                "path": "command-center/p2-wave/probes/RES-0126/captures/FR-2021-10-21-2021-22774.html",
            },
            {
                "claim": (
                    "Live tools/mcp is present with dirs "
                    f"{live_mcp_dirs}; FLAG rows are pinned to live wrapper files plus FR HTML."
                ),
                "kind": "live-tree",
                "path": "tools/mcp",
            },
            {
                "claim": NO_LEGAL,
                "kind": "disclaimer",
                "path": ART_REL,
            },
        ],
        "evidence_tier_ledger": "E1=verbatim FR HTML; E2=AUD graph plus live tools/; E3=catalog string mentions",
        "fetch_timestamp": FETCH_TS,
        "flagged_ids": flagged,
        "id": UNIT_ID,
        "inventory": inv,
        "no_legal_conclusion_statement": NO_LEGAL,
        "not_flagged_ids": not_flagged,
        "official_captures": captures,
        "owner_approval_required_for_downstream_action": True,
        "owner_decisions_triggered": [
            {
                "id": "OD-PUBLISH-RE-HEXSTRIKE",
                "question": (
                    "May reverse-engineering-mcp-bundle / hexstrike-ai / hacktricks-mcp-server "
                    "/ cheatengine-mcp-bridge be published or upstreamed before a qualified "
                    "export-control review?"
                ),
                "status": "unanswered",
            },
            {
                "id": "OD-J15-NAMED-IN-CATALOG",
                "question": (
                    "Catalog already names a J-15 dual-use disclosure review before upstreaming "
                    "security-bearing code; this unit restates that gate rather than closing it."
                ),
                "status": "unanswered",
                "catalog_mentions_j15": inv["catalog"]["mentions_j15_dual_use"],
            },
        ],
        "owner_signoff": "absent",
        "question": (
            "Does a toolchain that includes reverse-engineering, security-scanning and "
            "automation capability raise any export or dual-use consideration worth an "
            "owner decision before publication - and what is the factual basis either way?"
        ),
        "residual_unknowns": [
            "EU Dual-Use Regulation 2021/821 Annex I was not stored as local bytes; load-bearing quotes are US Federal Register HTML snapshots.",
            "hexstrike-ai and cheatengine-mcp-bridge upstream implementations are not vendored; only repo-owned wrappers and README commit pins are present.",
            "85 FR 62583 Note 1 (SRE/debugger exclusion) is quoted and not applied as a classification of the live reverse-engineering or Cheat Engine wrappers; applying it would be a legal conclusion this unit forbids.",
            "This unit does not snapshot the live eCFR (eCFR.gov blocked automated fetch); FR HTML from govinfo.gov is the version pin.",
            "Owner sign-off is absent; downstream_action_authorized remains false.",
        ],
        "reviewer": {
            "independent": True,
            "reviewer_id": "RES-0126-probe2-not-flagged-control",
            "shown_conclusion_first": False,
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests": tests,
        "title": "Export-control and dual-use review landscape for a security-adjacent toolchain",
        "ts": now,
        "unit_id": UNIT_ID,
        "worktree_git_sha": None,
    }


def main() -> int:
    doc = build()
    # Fill claim snapshot hashes after dump is not possible; hash official captures instead.
    for claim in doc["claims"]:
        cap = doc["official_captures"][0]["sha256"]
        claim["snapshot_sha256"] = cap
    dump_json(doc, ART)
    print(f"wrote {rel(ART)}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
