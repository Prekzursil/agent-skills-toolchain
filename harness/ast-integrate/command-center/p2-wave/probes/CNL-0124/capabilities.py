"""Closed council-capability inventory for CNL-0124.

Each row is a runtime capability a CouncilSpec compiler branches on, not a
preset and not every CNL unit. Mapping is either an existing workflow
primitive (catalog-cited) or a named required extension on the SAME plane.
Unmapped rows fail the inventory check.

The capability with no home on the current plane is CAP-STANDING
(trigger-woken persistence): HumanCheckpoint is owner-gated, not event-woken.
"""
from __future__ import annotations

from typing import Any

from plane import (
    ALLOWED_PRIMITIVES,
    EXTENSION_KINDS,
    catalog_units_by_id,
)

NO_HOME_ID = "CAP-STANDING"

# Closed set. home in ALLOWED_PRIMITIVES XOR required_extension in EXTENSION_KINDS
# (CAP-STANDING / CAP-VOTING / CAP-ANONYMITY are extensions).
CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "id": "CAP-ROSTER",
        "capability": "Role roster / per-seat WorkUnits",
        "catalog_id": "CNL-0005",
        "title_needle": "Participant descriptor type",
        "home": "DynamicFanOut",
        "compile_rule": "roles[] -> DynamicFanOut of WorkUnit templates with routing",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-INFO-PARTITION",
        "capability": "Information partition (who may see what, when)",
        "catalog_id": "CNL-0006",
        "title_needle": "Information-partition lattice",
        "home": "Subworkflow",
        "compile_rule": "isolated artifact namespace per Subworkflow / id_namespace",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-ANONYMITY",
        "capability": "Anonymity / identity blinding then reveal",
        "catalog_id": "CNL-0007",
        "title_needle": "Anonymity levels and their effect on attribution",
        "home": "",
        "compile_rule": "WorkUnit.routing is named; blinding is not a plane primitive",
        "required_extension": "BlindEnvelope",
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-BUDGET",
        "capability": "Budget block and exhaustion",
        "catalog_id": "CNL-0008",
        "title_needle": "Budget block",
        "home": "budget-rollup",
        "compile_rule": "child WorkUnit budgets roll up to the parent workflow",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-STOPPING",
        "capability": "Stopping expression and max rounds",
        "catalog_id": "CNL-0010",
        "title_needle": "Stopping-expression grammar",
        "home": "Loop",
        "compile_rule": "stopping.expression -> Loop.convergence_expr; max_rounds -> max_iterations",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-REPLAY",
        "capability": "Deterministic replay state",
        "catalog_id": "CNL-0011",
        "title_needle": "Replay state model",
        "home": "workflow-receipts",
        "compile_rule": "durable receipts + HumanCheckpoint pause_token; no resident process",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-CHAIR",
        "capability": "Chair / owner gate (pause, resume, override)",
        "catalog_id": "CNL-0025",
        "title_needle": "Chair powers and capture resistance",
        "home": "HumanCheckpoint",
        "compile_rule": "owner/chair decision is HumanCheckpoint, not a busy-wait loop",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-JURY",
        "capability": "Jury topology: deciders who did not argue",
        "catalog_id": "CNL-0034",
        "title_needle": "Jury topology",
        "home": "Pipeline",
        "compile_rule": "Pipeline: argue-Subworkflow -> Barrier -> decide-Subworkflow with hidden transcripts",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-NESTED",
        "capability": "Nested subcouncils / council-of-councils fan-in",
        "catalog_id": "CNL-0037",
        "title_needle": "Nested subcouncils and council-of-councils fan-in",
        "home": "Subworkflow",
        "compile_rule": "child CouncilSpec compiles to Subworkflow with namespaced ids",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-TURN-TAKING",
        "capability": "Turn-taking / speaking order",
        "catalog_id": "CNL-0047",
        "title_needle": "Turn-taking and speaking-order engine as one shared primitive",
        "home": "WorkUnit",
        "compile_rule": "dispatch order is the agentspec executor; council must not own a turn engine",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-PROTOCOL-SEQ",
        "capability": "Protocol composition: sequence",
        "catalog_id": "CNL-0050",
        "title_needle": "Protocol composition primitives",
        "home": "Pipeline",
        "compile_rule": "sequence -> Pipeline stages",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-PROTOCOL-SPLICE",
        "capability": "Protocol composition: splice",
        "catalog_id": "CNL-0050",
        "title_needle": "Protocol composition primitives",
        "home": "Pipeline",
        "compile_rule": "splice -> Pipeline stage insertion at an index",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-PROTOCOL-NEST",
        "capability": "Protocol composition: nest",
        "catalog_id": "CNL-0050",
        "title_needle": "Protocol composition primitives",
        "home": "Subworkflow",
        "compile_rule": "nest -> Subworkflow",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-PROTOCOL-REPEAT",
        "capability": "Protocol composition: repeat-until",
        "catalog_id": "CNL-0050",
        "title_needle": "Protocol composition primitives",
        "home": "Loop",
        "compile_rule": "repeat-until -> Loop with bound",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-DIVERGE-CONVERGE",
        "capability": "Divergence-before-convergence ordering",
        "catalog_id": "CNL-0050",
        "title_needle": "Protocol composition primitives",
        "home": "FanOut",
        "compile_rule": "compile-time FanOut then Barrier; reverse order is rejected",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-VOTING",
        "capability": "Ballot tabulation (majority / IRV / weighted / Condorcet)",
        "catalog_id": "CNL-0061",
        "title_needle": "Ranked-choice tabulation",
        "home": "",
        "compile_rule": "Barrier waits for completion; it does not rank ballots",
        "required_extension": "BallotReduce",
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-ORACLE",
        "capability": "Bound-oracle / evidence-outranks-popularity join",
        "catalog_id": "CNL-0068",
        "title_needle": "Evidence outranks popularity",
        "home": "Barrier",
        "compile_rule": "Barrier join policy oracle_gate; not a fifth vote and not a scheduler",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-MINORITY",
        "capability": "Minority-report conservation at emit",
        "catalog_id": "CNL-0070",
        "title_needle": "Minority report generation and mandatory preservation",
        "home": "completion-predicate",
        "compile_rule": "emit-gate on the shared completion predicate; keyed conservation",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
    {
        "id": "CAP-STANDING",
        "capability": "Standing watch: long-running, trigger-woken, low-intensity",
        "catalog_id": "CNL-0115",
        "title_needle": "Standing watch council",
        "home": "",
        "compile_rule": (
            "HumanCheckpoint is owner-gated pause. ETag/release-tag wake has no "
            "node. Required workflow-plane Watch; a council event loop is forbidden."
        ),
        "required_extension": "Watch",
        "needs_own_scheduler": False,
        "no_home_on_current_plane": True,
    },
    {
        "id": "CAP-ROUTING",
        "capability": "Per-seat vendor/model/role routing",
        "catalog_id": "IMP-0135",
        "title_needle": "per-unit model/vendor/role routing",
        "home": "routing",
        "compile_rule": "WorkUnit.routing resolves through rails.toml; no rival table",
        "required_extension": None,
        "needs_own_scheduler": False,
    },
)

REQUIRED_FAMILIES = {
    "roster": ("role", "seat", "participant", "roster"),
    "stopping": ("stopping",),
    "voting": ("vote", "tabulation", "majority", "ranked"),
    "anonymity": ("anonym",),
    "chair": ("chair",),
    "nest": ("nested", "subcouncil", "council-of-councils"),
    "standing": ("standing", "watch", "trigger-woken"),
    "minority": ("minority", "dissent"),
    "composition": ("sequence", "splice", "repeat-until"),
    "turn": ("turn-taking", "speaking-order"),
}


def classify(row: dict[str, Any]) -> str:
    home = str(row.get("home") or "")
    ext = row.get("required_extension")
    if home and home in ALLOWED_PRIMITIVES and not ext:
        return "mapped"
    if ext and ext in EXTENSION_KINDS and not home:
        return "required_extension"
    if home and ext:
        return "unmapped"
    return "unmapped"


def inventory_rows(rows: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    src = list(rows if rows is not None else CAPABILITIES)
    out = []
    for row in src:
        item = dict(row)
        item["class"] = classify(item)
        out.append(item)
    return out


def inventory_summary(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    items = rows if rows is not None else inventory_rows()
    mapped = [r for r in items if r["class"] == "mapped"]
    ext = [r for r in items if r["class"] == "required_extension"]
    unmapped = [r for r in items if r["class"] == "unmapped"]
    no_home = [r for r in items if r.get("no_home_on_current_plane")]
    return {
        "n_capabilities": len(items),
        "n_mapped": len(mapped),
        "n_required_extension": len(ext),
        "n_unmapped": len(unmapped),
        "mapped_ids": [r["id"] for r in mapped],
        "extension_ids": [r["id"] for r in ext],
        "unmapped_ids": [r["id"] for r in unmapped],
        "required_extensions_named": sorted(
            {r["required_extension"] for r in ext if r.get("required_extension")}
        ),
        "no_home_ids": [r["id"] for r in no_home],
        "no_home_capability": no_home[0]["id"] if no_home else None,
        "ok": len(unmapped) == 0 and len(items) > 0,
    }


def plant_unmapped(rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Negative control: a capability with neither primitive nor extension."""
    items = [dict(r) for r in (rows if rows is not None else inventory_rows())]
    items.append(
        {
            "id": "CAP-PLANTED-UNMAPPED",
            "capability": "planted: no primitive and not listed as extension",
            "catalog_id": "CNL-0124",
            "title_needle": "Council as a first-class workflow type",
            "home": "",
            "compile_rule": "planted mutant",
            "required_extension": None,
            "needs_own_scheduler": False,
            "class": "unmapped",
        }
    )
    items[-1]["class"] = classify(items[-1])
    return items


def verify_catalog_anchors() -> dict[str, Any]:
    units = catalog_units_by_id()
    misses: list[dict[str, str]] = []
    hits: list[dict[str, str]] = []
    for row in CAPABILITIES:
        uid = row["catalog_id"]
        u = units.get(uid)
        if not u:
            misses.append({"id": row["id"], "catalog_id": uid, "reason": "unit-absent"})
            continue
        title = str(u.get("title") or "")
        question = str(u.get("question_or_target") or "")
        needle = row["title_needle"]
        blob = title + " " + question
        if needle not in blob:
            misses.append(
                {
                    "id": row["id"],
                    "catalog_id": uid,
                    "reason": "needle-absent",
                    "needle": needle,
                    "title": title[:120],
                }
            )
        else:
            hits.append({"id": row["id"], "catalog_id": uid, "title": title})
    return {"hits": hits, "misses": misses, "ok": not misses}


def family_coverage() -> dict[str, Any]:
    blob = " ".join(
        f"{r['id']} {r['capability']} {r['title_needle']} {r['compile_rule']}".lower()
        for r in CAPABILITIES
    )
    missing = []
    present = []
    for family, tokens in REQUIRED_FAMILIES.items():
        if any(tok in blob for tok in tokens):
            present.append(family)
        else:
            missing.append(family)
    return {"present": present, "missing": missing, "ok": not missing}
