"""Independent checkers for RES-0045 claim record vs captured snapshots.

Probe 1: per-protocol unique-capability lists recomputed from snapshot bytes.
Probe 2: defensible DECLINE control, two-rail overclaim, mutants.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/RES-0045.json"
SNAP = HERE / "snapshots"
CAPTURE = SNAP / "CAPTURE.json"
UNIT_ID = "RES-0045"
SENTINEL = (
    "SUCCESS:RES-0045 in the receipt AND a per-protocol unique-capability list "
    "(possibly empty and explicitly marked so) plus a reasoned adopt/decline "
    "recommendation"
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
MEASURED_TIERS = frozenset({"E1", "E2"})
RAIL_KINDS = frozenset({"structured-api", "prose-source"})
RAIL_FIELDS = (
    "kind",
    "permalink",
    "fetch_timestamp",
    "http_status",
    "sha256",
    "snapshot",
)

# First-class identifiers. Unique iff present in own R1 and absent from MCP R1
# (for A2A / agent-connect) or absent from A2A+agent-connect R1 (for MCP).
A2A_CANDIDATES = [
    {
        "id": "agent-card-discovery",
        "token": "AgentCard",
        "name": "First-class Agent Card (peer identity, skills, endpoint)",
    },
    {
        "id": "extended-agent-card",
        "token": "GetExtendedAgentCard",
        "name": "Authenticated extended Agent Card RPC",
    },
    {
        "id": "task-push-notifications",
        "token": "CreateTaskPushNotificationConfig",
        "name": "Task push-notification webhook configuration",
    },
    {
        "id": "peer-send-message",
        "token": "rpc SendMessage",
        "name": "Peer SendMessage RPC (agent-to-agent, not tool-call)",
    },
]
MCP_CANDIDATES = [
    {
        "id": "sampling",
        "token": "sampling/createMessage",
        "name": "Client sampling (server asks host LLM to create a message)",
    },
    {
        "id": "elicitation",
        "token": "elicitation/create",
        "name": "Client elicitation (server asks host to gather user input)",
    },
    {
        "id": "tools-call",
        "token": "tools/call",
        "name": "First-class tools/call (host-mediated tool invocation)",
    },
    {
        "id": "resources-read",
        "token": "resources/read",
        "name": "URI resources/read (host-mediated data access)",
    },
    {
        "id": "roots-list",
        "token": "roots/list",
        "name": "Client roots/list (workspace root disclosure)",
    },
]
AGENT_CONNECT_CANDIDATES = [
    {
        "id": "run-wait",
        "token": "/runs/{run_id}/wait",
        "name": "REST blocking wait on an agent run",
    },
    {
        "id": "threads",
        "token": "/threads/{thread_id}",
        "name": "REST thread resource for stateful multi-run sessions",
    },
    {
        "id": "agent-descriptor",
        "token": "/agents/{agent_id}/descriptor",
        "name": "GET agent descriptor (Agent Connect Protocol)",
    },
    {
        "id": "run-cancel",
        "token": "/runs/{run_id}/cancel",
        "name": "REST cancel of an agent run",
    },
    {
        "id": "ibm-run-events",
        "token": "/runs/{run_id}/events",
        "name": "REST run event stream (IBM ACP)",
    },
]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_art(path: Path | None = None) -> dict:
    return json.loads((path or ART).read_text(encoding="utf-8"))


def load_capture() -> dict:
    return json.loads(CAPTURE.read_text(encoding="utf-8"))


def snap_text(name: str) -> str:
    return (SNAP / name).read_bytes().decode("utf-8", "replace")


def haystacks() -> dict[str, str]:
    return {
        "mcp": snap_text("r1-mcp-schema-2026-07-28.json"),
        "a2a": snap_text("r1-a2a.proto"),
        "agntcy": snap_text("r1-agntcy-acp-openapi.json"),
        "ibm_acp": snap_text("r1-ibm-acp-openapi.yaml"),
    }


def present(token: str, text: str) -> bool:
    return token in text


def unique_from_snapshots() -> dict:
    h = haystacks()
    mcp_r1 = h["mcp"]
    a2a_r1 = h["a2a"]
    acp_r1 = h["agntcy"] + "\n" + h["ibm_acp"]
    others_vs_mcp = a2a_r1 + "\n" + acp_r1

    def pick(cands: list[dict], own: str, contra: str) -> dict:
        found = []
        missing_in_own = []
        for row in cands:
            if not present(row["token"], own):
                missing_in_own.append(row["id"])
                continue
            if present(row["token"], contra):
                continue
            found.append(
                {
                    "id": row["id"],
                    "token": row["token"],
                    "name": row["name"],
                    "none_found": False,
                }
            )
        none = len(found) == 0
        return {
            "capabilities": found,
            "none_found": none,
            "none_found": none,
            "candidates_absent_from_own_spec": missing_in_own,
        }

    return {
        "mcp": pick(MCP_CANDIDATES, mcp_r1, others_vs_mcp),
        "a2a": pick(A2A_CANDIDATES, a2a_r1, mcp_r1),
        "agent_connect": pick(AGENT_CONNECT_CANDIDATES, acp_r1, mcp_r1),
    }


def rail_errors(rail: dict, require_200: bool = True) -> list[str]:
    errs: list[str] = []
    if not isinstance(rail, dict):
        return ["rail-not-object"]
    for field in RAIL_FIELDS:
        if not rail.get(field):
            errs.append(f"rail-missing-{field}")
    kind = str(rail.get("kind") or "")
    if kind not in RAIL_KINDS:
        errs.append(f"rail-bad-kind:{kind}")
    status = rail.get("http_status")
    if require_200 and status != 200:
        errs.append(f"rail-http:{status}")
    snap_rel = str(rail.get("snapshot") or "").replace("\\", "/")
    sha = str(rail.get("sha256") or "")
    if snap_rel and sha:
        path = REPO / snap_rel
        if not path.is_file():
            errs.append(f"snapshot-absent:{snap_rel}")
        else:
            live = sha256_bytes(path.read_bytes())
            if live != sha:
                errs.append(f"snapshot-sha-mismatch:{snap_rel}")
            size = rail.get("captured_bytes")
            if isinstance(size, int) and size != path.stat().st_size:
                errs.append(f"snapshot-bytes-mismatch:{snap_rel}")
    return errs


def claim_kinds(claim: dict) -> set[str]:
    return {str(r.get("kind")) for r in (claim.get("rails") or []) if isinstance(r, dict)}


def two_rail_errors(claim: dict) -> list[str]:
    cid = str(claim.get("id") or "?")
    errs: list[str] = []
    rails = claim.get("rails") or []
    if not isinstance(rails, list) or len(rails) < 2:
        errs.append(f"{cid}:need-two-rails")
        return errs
    kinds = claim_kinds(claim)
    if "structured-api" not in kinds:
        errs.append(f"{cid}:missing-structured-api-rail")
    if "prose-source" not in kinds:
        errs.append(f"{cid}:missing-prose-source-rail")
    for i, rail in enumerate(rails):
        for e in rail_errors(rail):
            errs.append(f"{cid}:rail[{i}]:{e}")
    if not claim.get("source_lineage"):
        errs.append(f"{cid}:missing-source_lineage")
    return errs


def sentinel_state_errors(doc: dict) -> list[str]:
    errs: list[str] = []
    text = json.dumps(doc, ensure_ascii=True)
    if SENTINEL not in text:
        errs.append("sentinel-absent-from-artifact")
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        errs.append(f"self-declared:{state}")
    if str(doc.get("unit_id") or "") != UNIT_ID:
        errs.append("unit_id")
    receipt = doc.get("receipt")
    if not isinstance(receipt, dict) or SENTINEL not in str(receipt.get("line") or ""):
        errs.append("sentinel-not-in-receipt")
    return errs


def unique_list_errors(doc: dict, live: dict | None = None) -> list[str]:
    errs: list[str] = []
    live = live or unique_from_snapshots()
    lists = doc.get("unique_capability_lists") or doc.get("per_protocol_unique_capabilities")
    if not isinstance(lists, dict):
        return ["unique-capability-lists-absent"]
    for proto in ("mcp", "a2a", "agent_connect"):
        row = lists.get(proto)
        if not isinstance(row, dict):
            errs.append(f"{proto}:list-absent")
            continue
        caps = row.get("capabilities")
        none = row.get("none_found")
        if none is None:
            none = row.get("none_found")
        if none is True:
            if isinstance(caps, list) and len(caps) > 0:
                errs.append(f"{proto}:none-found-but-capabilities-present")
            continue
        if not isinstance(caps, list) or len(caps) < 1:
            errs.append(f"{proto}:empty-without-none_found")
            continue
        live_ids = {c["id"] for c in live[proto]["capabilities"]}
        art_ids = {c.get("id") for c in caps if isinstance(c, dict)}
        if art_ids != live_ids:
            errs.append(f"{proto}:list-mismatch art={sorted(art_ids)} live={sorted(live_ids)}")
        for cap in caps:
            token = str(cap.get("token") or "")
            if not token:
                errs.append(f"{proto}:{cap.get('id')}:missing-token")
    # Catalog test: name at least one unique capability per protocol, or NONE-FOUND.
    for proto in ("mcp", "a2a", "agent_connect"):
        row = lists.get(proto) or {}
        if row.get("none_found") is True or row.get("none_found") is True:
            continue
        if not (row.get("capabilities") or []):
            errs.append(f"{proto}:neither-capability-nor-none-found")
    return errs


def claim_record_errors(doc: dict) -> list[str]:
    errs: list[str] = []
    claims = doc.get("claims") or []
    if not isinstance(claims, list) or len(claims) < 3:
        return ["claims-too-few"]
    measured = 0
    for claim in claims:
        if not isinstance(claim, dict):
            errs.append("claim-not-object")
            continue
        cid = str(claim.get("id") or "?")
        for field in (
            "id",
            "canonical_mechanism",
            "source_lineage",
            "evidence_tier",
            "confidence_band",
            "settling_probe",
            "freshness_stamp",
            "verdict",
            "strongest_caveat",
        ):
            if not claim.get(field):
                errs.append(f"{cid}:missing-{field}")
        tier = str(claim.get("evidence_tier") or "")
        verdict = str(claim.get("verdict") or "")
        if verdict == "CONFIRMED" and tier in MEASURED_TIERS:
            measured += 1
            errs.extend(two_rail_errors(claim))
            if claim.get("citable_as_measured_fact") is not True:
                errs.append(f"{cid}:e2-not-marked-citable")
        if verdict == "CONFIRMED" and tier == "E3":
            if claim.get("citable_as_measured_fact") is True:
                errs.append(f"{cid}:e3-cited-as-measured-fact")
        if verdict == "CONFIRMED" and not claim.get("strongest_caveat"):
            errs.append(f"{cid}:missing-caveat")
    if measured < 2:
        errs.append(f"measured-confirmed-too-few:{measured}")
    return errs


def recommendation_errors(doc: dict) -> list[str]:
    errs: list[str] = []
    rec = doc.get("recommendation") or {}
    if not isinstance(rec, dict):
        return ["recommendation-absent"]
    verdict = str(rec.get("verdict") or rec.get("adopt_or_decline") or "").upper()
    if verdict not in {"DECLINE", "NO", "DO-NOT-ADOPT"}:
        errs.append(f"recommendation-not-decline:{verdict!r}")
    lost = str(
        rec.get("capability_lost_if_declined")
        or rec.get("capability_lost_by_declining")
        or ""
    )
    if len(lost) < 24:
        errs.append("capability-lost-if-declined-too-short")
    rationale = str(rec.get("rationale") or rec.get("reason") or "")
    if len(rationale) < 40:
        errs.append("recommendation-rationale-too-short")
    if rec.get("defensible_no") is not True and rec.get("control_no_fired") is not True:
        if rec.get("defensible_no") is not True and rec.get("control_no_fired") is not True:
            if not re.search(r"\bNO\b", str(doc.get("answer") or ""), re.I):
                errs.append("defensible-no-not-recorded")
    answer = str(doc.get("answer") or "").lower()
    if "second adapter" not in answer and "second protocol" not in answer and "decline" not in answer:
        if "no" not in answer:
            errs.append("answer-missing-no-or-decline")
    return errs


def capture_index_errors() -> list[str]:
    errs: list[str] = []
    if not CAPTURE.is_file():
        return ["capture-index-absent"]
    cap = load_capture()
    rails = cap.get("rails") or []
    if len(rails) < 8:
        errs.append(f"capture-rails-too-few:{len(rails)}")
    kinds = {str(r.get("kind")) for r in rails if isinstance(r, dict)}
    if "structured-api" not in kinds or "prose-source" not in kinds:
        errs.append("capture-missing-rail-kind")
    for rail in rails:
        if not isinstance(rail, dict):
            continue
        errs.extend(rail_errors(rail))
    return errs


def validate_unique_caps(doc: dict) -> list[str]:
    return (
        sentinel_state_errors(doc)
        + capture_index_errors()
        + unique_list_errors(doc)
        + claim_record_errors(doc)
    )


def validate_decline_control(doc: dict) -> list[str]:
    return (
        sentinel_state_errors(doc)
        + claim_record_errors(doc)
        + unique_list_errors(doc)
        + recommendation_errors(doc)
    )


def mutant_drop_rail_accepted(doc: dict) -> bool:
    mutant = copy.deepcopy(doc)
    dropped = False
    for claim in mutant.get("claims") or []:
        if (
            claim.get("verdict") == "CONFIRMED"
            and str(claim.get("evidence_tier") or "") in MEASURED_TIERS
            and isinstance(claim.get("rails"), list)
            and len(claim["rails"]) >= 2
        ):
            claim["rails"] = claim["rails"][:1]
            dropped = True
            break
    if not dropped:
        return True
    return not claim_record_errors(mutant)


def mutant_drop_unique_list_accepted(doc: dict) -> bool:
    mutant = copy.deepcopy(doc)
    lists = mutant.get("unique_capability_lists")
    if not isinstance(lists, dict) or "a2a" not in lists:
        return True
    lists["a2a"] = {"capabilities": [], "none_found": False}
    return not unique_list_errors(mutant)


def mutant_adopt_without_loss_accepted(doc: dict) -> bool:
    mutant = copy.deepcopy(doc)
    rec = mutant.get("recommendation")
    if not isinstance(rec, dict):
        return True
    rec["verdict"] = "ADOPT"
    rec["defensible_no"] = False
    rec["capability_lost_if_declined"] = ""
    mutant["answer"] = "Adopt a second adapter."
    return not recommendation_errors(mutant)


def mutant_e3_cited_as_fact_accepted(doc: dict) -> bool:
    mutant = copy.deepcopy(doc)
    marked = False
    for claim in mutant.get("claims") or []:
        if str(claim.get("evidence_tier") or "") == "E3":
            claim["citable_as_measured_fact"] = True
            claim["verdict"] = "CONFIRMED"
            marked = True
            break
    if not marked:
        mutant.setdefault("claims", []).append(
            {
                "id": "MUTANT-E3",
                "canonical_mechanism": "synthetic",
                "source_lineage": "one rail only",
                "evidence_tier": "E3",
                "confidence_band": "LOW",
                "settling_probe": "none",
                "freshness_stamp": "2026-08-24T00:00:00Z",
                "verdict": "CONFIRMED",
                "strongest_caveat": "synthetic",
                "citable_as_measured_fact": True,
                "rails": [],
            }
        )
    return not claim_record_errors(mutant)


unique_from_snapshots = unique_from_snapshots
validate_unique_caps = validate_unique_caps
validate_decline_control = validate_decline_control
mutant_drop_rail_accepted = mutant_drop_rail_accepted
mutant_drop_unique_list_accepted = mutant_drop_unique_list_accepted
mutant_adopt_without_loss_accepted = mutant_adopt_without_loss_accepted
mutant_e3_cited_as_fact_accepted = mutant_e3_cited_as_fact_accepted
recommendation_errors = recommendation_errors
load_capture = load_capture
load_art = load_art
