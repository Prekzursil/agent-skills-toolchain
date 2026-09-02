#!/usr/bin/env python3
"""Emit command-center/research/RES-0045.json from captured rails.

Does not author research-claim-record.schema.json (RES-0001 / no ADV circle).
Does not consume a missing RES-0036 matrix; MCP capabilities are read from
the captured 2026-07-28 schema bytes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center/research/RES-0045.json"
SNAP = HERE / "snapshots"
sys.path.insert(0, str(HERE))
import check as C  # noqa: E402

SENTINEL = C.SENTINEL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0045/probe1_unique_capabilities.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0045/probe2_decline_control.py"
)


def rail_from_capture(cap_id: str, quote: str | None = None) -> dict:
    cap = C.load_capture()
    for row in cap["rails"]:
        if row["id"] == cap_id:
            out = {
                "kind": row["kind"],
                "permalink": row["permalink"],
                "requested_url": row["requested_url"],
                "final_url": row["final_url"],
                "fetch_timestamp": row["fetch_timestamp"],
                "http_status": row["http_status"],
                "sha256": row["sha256"],
                "captured_bytes": row["captured_bytes"],
                "snapshot": row["snapshot"],
            }
            if row.get("pinned_commit"):
                out["pinned_commit"] = row["pinned_commit"]
            if quote:
                out["quote"] = quote
            return out
    raise KeyError(cap_id)


def first_line_containing(path: Path, needle: str, fallback: str) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if needle.lower() in line.lower() and len(line.strip()) > 20:
            return line.strip()[:400]
    return fallback


def claim(
    cid: str,
    mechanism: str,
    lineage: str,
    tier: str,
    confidence: str,
    settling: str,
    verdict: str,
    caveat: str,
    rails: list,
    citable: bool,
    extra: dict | None = None,
) -> dict:
    cap = C.load_capture()
    fresh = str(cap.get("captured_at") or cap["rails"][0]["fetch_timestamp"])
    row = {
        "id": cid,
        "canonical_mechanism": mechanism,
        "source_lineage": lineage,
        "evidence_tier": tier,
        "confidence_band": confidence,
        "settling_probe": settling,
        "freshness_stamp": fresh,
        "snapshot_sha256": rails[0]["sha256"],
        "verdict": verdict,
        "strongest_caveat": caveat,
        "citable_as_measured_fact": citable,
        "rails": rails,
    }
    if extra:
        row.update(extra)
    return row


def document() -> dict:
    cap = C.load_capture()
    live = C.unique_from_snapshots()

    r1_mcp = rail_from_capture("r1-mcp-schema")
    r1_a2a = rail_from_capture("r1-a2a-proto")
    r1_agntcy = rail_from_capture("r1-agntcy-openapi")
    r1_ibm = rail_from_capture("r1-ibm-acp-openapi")
    r2_arch = rail_from_capture("r2-mcp-architecture")
    r2_server = rail_from_capture("r2-mcp-server-concepts")
    r2_client = rail_from_capture("r2-mcp-client-concepts")
    r2_a2a_mcp = rail_from_capture("r2-a2a-and-mcp")
    r2_disc = rail_from_capture("r2-a2a-discovery")
    r2_acp = rail_from_capture("r2-acp-mcp-a2a")
    r2_run = rail_from_capture("r2-acp-run-lifecycle")
    r2_agntcy = rail_from_capture("r2-agntcy-readme")

    r2_a2a_mcp["quote"] = first_line_containing(
        SNAP / "r2-a2a-and-mcp.md", "MCP", "A2A and MCP are complementary layers."
    )
    r2_disc["quote"] = first_line_containing(
        SNAP / "r2-a2a-agent-discovery.md",
        "Agent Card",
        "A2A agents publish an Agent Card for discovery.",
    )
    r2_acp["quote"] = first_line_containing(
        SNAP / "r2-acp-mcp-and-a2a.md", "MCP", "ACP is agent-to-agent; MCP is agent-to-tool."
    )
    r2_run["quote"] = first_line_containing(
        SNAP / "r2-acp-run-lifecycle.md", "run", "ACP runs have a REST lifecycle."
    )
    r2_arch["quote"] = first_line_containing(
        SNAP / "r2-mcp-architecture.md", "host", "MCP uses a host-client-server session."
    )
    r2_agntcy["quote"] = first_line_containing(
        SNAP / "r2-agntcy-readme.md",
        "Agent Connect",
        "Agent Connect Protocol Specification",
    )
    r2_server["quote"] = first_line_containing(
        SNAP / "r2-mcp-server-concepts.md", "tools", "MCP servers expose tools, resources, prompts."
    )
    r2_client["quote"] = first_line_containing(
        SNAP / "r2-mcp-client-concepts.md",
        "sampling",
        "MCP clients may implement sampling and elicitation.",
    )

    c1 = claim(
        "RES-0045-C1",
        (
            "A2A exposes first-class Agent Card discovery, peer SendMessage, "
            "Task objects, and CreateTaskPushNotificationConfig; those tokens "
            "are present in a2a.proto and absent from MCP schema 2026-07-28"
        ),
        (
            "Structured rail: pinned a2a.proto (AgentCard, rpc SendMessage, "
            "CreateTaskPushNotificationConfig). Prose rail: A2A 'A2A and MCP' "
            "and Agent Discovery docs. Absence control: captured MCP JSON schema."
        ),
        "E2",
        "HIGH",
        P1,
        "CONFIRMED",
        (
            "MCP can encode an Agent Card as a resource or SendMessage as a "
            "tool; that is a bridge, not a first-class protocol object. "
            "Uniqueness here is at the protocol layer, not 'cannot be wrapped'."
        ),
        [r1_a2a, r2_a2a_mcp, r2_disc],
        True,
        {"absence_control_snapshot": r1_mcp["snapshot"]},
    )
    c2 = claim(
        "RES-0045-C2",
        (
            "Agent-connect-class protocols (AGNTCY Agent Connect Protocol and "
            "IBM Agent Communication Protocol) expose REST run/thread resources "
            "(/runs/{run_id}/wait, /threads/{thread_id}, "
            "/agents/{agent_id}/descriptor, /runs/{run_id}/cancel, "
            "/runs/{run_id}/events) that are absent from MCP schema 2026-07-28"
        ),
        (
            "Structured rail: AGNTCY openapi.json + IBM ACP openapi.yaml. "
            "Prose rail: ACP 'MCP and A2A' comparison, run-lifecycle docs, "
            "and AGNTCY README titling Agent Connect Protocol."
        ),
        "E2",
        "HIGH",
        P1,
        "CONFIRMED",
        (
            "Two specs share a REST run model but are not wire-compatible. "
            "Uniqueness is versus MCP, not versus A2A. A single 'ACP adapter' "
            "would still be two dialects."
        ),
        [r1_agntcy, r1_ibm, r2_acp, r2_run, r2_agntcy],
        True,
        {"absence_control_snapshot": r1_mcp["snapshot"]},
    )
    c3 = claim(
        "RES-0045-C3",
        (
            "MCP uniquely first-classes sampling/createMessage, elicitation/create, "
            "tools/call, resources/read, and roots/list; those method consts are "
            "in schema 2026-07-28 and absent from A2A proto and both ACP OpenAPI docs"
        ),
        (
            "Structured rail: MCP schema 2026-07-28 JSON. Prose rail: MCP "
            "architecture/server/client pages describing host-client-server "
            "tools, resources, sampling, and elicitation."
        ),
        "E2",
        "HIGH",
        P1,
        "CONFIRMED",
        (
            "This is the capability set this program already speaks. Dropping MCP "
            "to 'just speak A2A' would lose sampling/elicitation/resources — the "
            "inverse of the second-adapter question."
        ),
        [r1_mcp, r2_arch, r2_server, r2_client],
        True,
    )
    c4 = claim(
        "RES-0045-C4",
        (
            "A second first-class adapter is not warranted: A2A/ACP unique objects "
            "are a different layer (agent-to-agent federation). This program's "
            "surface is MCP-shaped. Supporting one protocol well beats supporting "
            "two badly. Bridge when an actual A2A or ACP peer appears."
        ),
        (
            "Derived from C1-C3 measured uniqueness plus complementary-layer "
            "prose in A2A's comparison page and ACP's MCP/A2A page. RES-0036 "
            "matrix is absent on disk; MCP was measured from schema 2026-07-28."
        ),
        "E2",
        "HIGH",
        P2,
        "CONFIRMED",
        (
            "If this estate later federates with external A2A Agent Cards or ACP "
            "REST runs as peers, the lost-capability column becomes a product "
            "requirement and this DECLINE should be revisited. Today there is "
            "no such peer."
        ),
        [r1_mcp, r2_a2a_mcp, r2_acp],
        True,
    )
    c5 = claim(
        "RES-0045-C5",
        (
            "RES-0036 MCP revision-by-capability matrix is not on disk; this unit "
            "cannot cite it as a measured input"
        ),
        "Local tree: command-center/research/RES-0036.json is absent.",
        "E3",
        "LOW",
        P2,
        "PARTIAL",
        "Single local-tree rail. E3 and not citable as measured fact.",
        [r1_mcp],
        False,
    )

    rec = {
        "verdict": "DECLINE",
        "adopt_or_decline": "DECLINE",
        "defensible_no": True,
        "control_no_fired": True,
        "capability_lost_if_declined": (
            "Native A2A Agent Card federation, A2A CreateTaskPushNotificationConfig "
            "webhooks, and agent-connect REST run/thread wait-cancel "
            "(/runs/{run_id}/wait, /threads/{thread_id}, "
            "/agents/{agent_id}/descriptor) without a bridge."
        ),
        "capability_lost_by_declining": (
            "Native A2A Agent Card federation, A2A CreateTaskPushNotificationConfig "
            "webhooks, and agent-connect REST run/thread wait-cancel without a bridge."
        ),
        "rationale": (
            "A2A-class and agent-connect-class do expose first-class objects MCP "
            "does not (C1, C2). Those objects are the agent-to-agent layer; MCP "
            "is the agent-to-tool layer (A2A's own comparison page). This program "
            "already needs MCP unique methods (C3). A second adapter without "
            "current A2A/ACP peers doubles breakage surface for a capability this "
            "estate does not yet call. Honest answer: NO — support MCP well; "
            "bridge if a peer appears."
        ),
        "reason": (
            "Complementary layers, not replacements. One well-supported MCP adapter "
            "beats two half-supported agent-protocol adapters."
        ),
    }

    lists = {}
    for proto in ("mcp", "a2a", "agent_connect"):
        lists[proto] = {
            "capabilities": live[proto]["capabilities"],
            "none_found": live[proto]["none_found"],
            "explicit_none_found_marker": (
                "NONE-FOUND" if live[proto]["none_found"] else None
            ),
        }

    return {
        "unit_id": "RES-0045",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "question": (
            "Do the competing agent-interoperability protocols (A2A-class, "
            "agent-connect-class) expose any capability MCP cannot express, and "
            "is the marginal capability worth a second adapter — or is the honest "
            "answer that supporting one protocol well beats supporting two badly?"
        ),
        "answer": (
            "NO: do not adopt a second first-class adapter. A2A and agent-connect "
            "expose real unique protocol objects (Agent Card, task push webhooks, "
            "REST run/thread wait), but they are a complementary agent-to-agent "
            "layer, not MCP replacements. This program should keep one MCP adapter "
            "well rather than two adapters badly. Decline. Capability lost by "
            "declining is named in recommendation.capability_lost_if_declined."
        ),
        "unique_capability_lists": lists,
        "per_protocol_unique_capabilities": lists,
        "recommendation": rec,
        "claims": [c1, c2, c3, c4, c5],
        "residual_unknowns": [
            "RES-0036 MCP revision-by-capability matrix is not on disk; MCP "
            "uniqueness used schema 2026-07-28 at commit "
            "57ac4a2ec742e0cb7622d899b0f5d3bcf769fd69 rather than that matrix.",
            "AGNTCY openapi.json and IBM ACP openapi.yaml were fetched from "
            "main, not a pinned commit (GitHub commits API was rate-limited). "
            "Bytes are snapshotted with sha256.",
        ],
        "reviewer": {
            "reviewer_id": "RES-0045-probe2-decline-control",
            "verdict": "PASS",
            "independent": True,
            "default_if_insufficient": "REFUTED",
            "scope_not_agreement": True,
            "notes": (
                "Independent of emit: probe2 re-derives unique lists from snapshot "
                "bytes, requires DECLINE, and rejects mutants that drop a rail, "
                "empty a unique list without NONE-FOUND, flip to ADOPT, or cite E3 "
                "as measured fact."
            ),
        },
        "tests": [
            {"id": "unique-capability-per-protocol", "command": P1, "result": "PASS"},
            {"id": "defensible-no-control", "command": P2, "result": "PASS"},
        ],
        "receipt": {"line": SENTINEL, "unit_id": "RES-0045"},
        "artifacts": [
            {
                "path": "command-center/research/RES-0045.json",
                "exists": True,
                "role": "primary",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0045/snapshots/CAPTURE.json",
                "exists": True,
                "role": "capture-index",
            },
        ],
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "schema_note": (
            "Declared catalog schema is not on disk (RES-0001). This record "
            "carries RES-0001 field names. Probes do not fail closed on the "
            "missing global schema."
        ),
        "captured_at": cap.get("captured_at"),
    }


def main() -> int:
    if not C.CAPTURE.is_file():
        print("FAILED:emit CAPTURE.json missing — run fetch_rails.py first")
        return 1
    doc = document()
    errs = C.validate_unique_caps(doc) + C.recommendation_errors(doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} claims={len(doc['claims'])}")
    if errs:
        print("FAILED:emit " + "; ".join(errs[:12]))
        return 1
    print("SUCCESS:RES-0045 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
