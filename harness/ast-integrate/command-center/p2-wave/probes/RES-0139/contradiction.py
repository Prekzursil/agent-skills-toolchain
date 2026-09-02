#!/usr/bin/env python3
"""Contradiction checker: planned contracts vs pinned published MUSTs.

A hit requires a named rule to fire. The checker is silent on unrelated
clauses (negative control) and must fire on a polarity-inverting mutant
(positive/sensitivity control).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

sys.path.insert(0, str(HERE))
import adapter as A  # noqa: E402

# Each rule quotes the published requirement it defends and names the
# contract-text pattern that would invert it.
RULES: list[dict] = [
    {
        "id": "MCP-LIFECYCLE-INIT-FIRST",
        "requirement_id": "mcp.lifecycle.initialization-first",
        "normative_quote": (
            "The initialization phase MUST be the first interaction between "
            "client and server."
        ),
        "keyword": "MUST",
        "section": "MCP Specification 2025-03-26 / Lifecycle / Initialization",
        "pattern": re.compile(
            r"(?is)(skip|omit|bypass|not required).{0,48}initializ"
            r"|(?:invoked|invoke|called|sent)\s+before\s+initializ"
            r"|before\s+initializ.{0,24}(tool|request|message)"
            r"|tool.{0,24}(?:may|can|allowed).{0,24}before.{0,16}initializ"
        ),
    },
    {
        "id": "MCP-JSONRPC-ID-NOT-NULL",
        "requirement_id": "mcp.basic.id-must-not-null",
        "normative_quote": "Unlike base JSON-RPC, the ID MUST NOT be `null`.",
        "keyword": "MUST NOT",
        "section": "MCP Specification 2025-03-26 / Base protocol / Requests",
        "pattern": re.compile(
            r"(?is)(?:mcp|json-rpc).{0,80}(?:id.{0,32}(?:may|can|allowed to be) null"
            r"|null.{0,20}(?:request )?id)"
        ),
    },
    {
        "id": "MCP-RECEIVE-BATCHES",
        "requirement_id": "mcp.basic.receive-batches",
        "normative_quote": (
            "MCP implementations MAY support sending JSON-RPC batches, but "
            "MUST support receiving JSON-RPC batches."
        ),
        "keyword": "MUST",
        "section": "MCP Specification 2025-03-26 / Base protocol / Batching",
        "pattern": re.compile(
            r"(?is)(?:must not|need not|not required to|optional to)\s+"
            r"(?:support\s+)?receiv.{0,24}batch"
        ),
    },
    {
        "id": "MCP-STDIO-NO-EMBEDDED-NEWLINES",
        "requirement_id": "mcp.transports.stdio-no-embedded-newlines",
        "normative_quote": (
            "Messages are delimited by newlines, and MUST NOT contain "
            "embedded newlines."
        ),
        "keyword": "MUST NOT",
        "section": "MCP Specification 2025-03-26 / Transports / stdio",
        "pattern": re.compile(
            r"(?is)(?:stdio.{0,80})?(?:may|can|allowed to) contain embedded newlines"
        ),
    },
    {
        "id": "RFC8174-UPPERCASE-ONLY",
        "requirement_id": "ietf.rfc8174.uppercase-only",
        "normative_quote": (
            "only UPPERCASE usage of the key words have the defined special "
            "meanings."
        ),
        "keyword": "n/a (clarifies BCP 14)",
        "section": "RFC 8174 Abstract / §2",
        "pattern": re.compile(
            r"(?is)lowercase (?:must|shall|should).{0,48}"
            r"(?:rfc 2119|bcp 14|normative key)"
        ),
    },
    {
        "id": "SLSA-L2-PROVENANCE-AUTHENTIC",
        "requirement_id": "slsa.v1.0.provenance-authentic",
        "normative_quote": (
            "Consumers MUST be able to validate the authenticity of the "
            "provenance attestation"
        ),
        "keyword": "MUST",
        "section": "SLSA v1.0 Producing artifacts / Provenance is Authentic (L2)",
        "pattern": re.compile(
            r"(?is)slsa (?:build )?l2.{0,80}(unsigned|without (?:a )?signatur)"
            r"|unsigned provenance.{0,40}slsa (?:build )?l2"
        ),
    },
]


CONTROLS = {
    "complying": {
        "id": "CTRL-COMPLY-MCP-INIT",
        "contract_id": "control.complying-mcp-initialize-first",
        "title": "Known-complying restatement of MCP initialize-first",
        "text": (
            "The initialization phase MUST be the first interaction between "
            "client and server. The client MUST send initialize before any "
            "tool call. Request ids MUST NOT be null. JSON-RPC messages MUST "
            "be UTF-8 encoded. stdio MCP messages MUST NOT contain embedded "
            "newlines. BCP 14 key words have their special meanings only when "
            "UPPERCASE."
        ),
    },
    "mutant": {
        "id": "CTRL-MUTANT-SKIP-INIT",
        "contract_id": "control.mutant-skip-initialize",
        "title": "Polarity-inverting mutant (must fire)",
        "text": (
            "MCP tools MAY be invoked before initialize; the initialization "
            "phase MAY be skipped. JSON-RPC request ids MAY be null. "
            "Implementations are not required to receive JSON-RPC batches. "
            "stdio MCP messages MAY contain embedded newlines. lowercase must "
            "and should SHALL be interpreted as RFC 2119 key words. SLSA L2 "
            "MAY ship unsigned provenance."
        ),
    },
}


def planned_phase4_contracts() -> list[dict]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    out = []
    for unit in data.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        if str(unit.get("phase")) != "4":
            continue
        path = str(unit.get("output_path") or "").replace("\\", "/")
        if not path.startswith("command-center/phase4/contracts/"):
            continue
        tests = unit.get("tests_required") or []
        test_text = " ".join(str(t) for t in tests)
        clause = str(unit.get("question_or_target") or "")
        out.append(
            {
                "id": unit.get("id"),
                "title": unit.get("title"),
                "output_path": path,
                "text": clause + "\n" + test_text,
                "clause": clause,
                "tests_required": tests,
            }
        )
    return out


def scan_text(contract_id: str, title: str, text: str) -> list[dict]:
    hits = []
    for rule in RULES:
        if not rule["pattern"].search(text or ""):
            continue
        m = rule["pattern"].search(text or "")
        hits.append(
            {
                "rule_id": rule["id"],
                "requirement_id": rule["requirement_id"],
                "contract_id": contract_id,
                "contract_title": title,
                "keyword": rule["keyword"],
                "section": rule["section"],
                "normative_quote": rule["normative_quote"],
                "contract_quote": (m.group(0) if m else text)[:400],
                "contract_text_excerpt": (text or "")[:800],
            }
        )
    return hits


def scan_contracts(contracts: list[dict]) -> list[dict]:
    hits: list[dict] = []
    for c in contracts:
        hits.extend(
            scan_text(
                str(c.get("id") or c.get("contract_id")),
                str(c.get("title") or ""),
                str(c.get("text") or c.get("clause") or ""),
            )
        )
    return hits


def evaluate() -> dict:
    planned = planned_phase4_contracts()
    production = scan_contracts(planned)
    comply_hits = scan_text(
        CONTROLS["complying"]["contract_id"],
        CONTROLS["complying"]["title"],
        CONTROLS["complying"]["text"],
    )
    mutant_hits = scan_text(
        CONTROLS["mutant"]["contract_id"],
        CONTROLS["mutant"]["title"],
        CONTROLS["mutant"]["text"],
    )
    return {
        "rules": [
            {
                "id": r["id"],
                "requirement_id": r["requirement_id"],
                "section": r["section"],
                "keyword": r["keyword"],
                "normative_quote": r["normative_quote"],
            }
            for r in RULES
        ],
        "planned_contract_count": len(planned),
        "planned_contract_ids": [c["id"] for c in planned],
        "production_hits": production,
        "production_hit_count": len(production),
        "negative_control": {
            **CONTROLS["complying"],
            "hits": comply_hits,
            "hit_count": len(comply_hits),
            "pass": len(comply_hits) == 0,
        },
        "mutant_control": {
            **CONTROLS["mutant"],
            "hits": mutant_hits,
            "hit_count": len(mutant_hits),
            "pass": len(mutant_hits) >= 1,
            "fired_rule_ids": [h["rule_id"] for h in mutant_hits],
        },
    }
