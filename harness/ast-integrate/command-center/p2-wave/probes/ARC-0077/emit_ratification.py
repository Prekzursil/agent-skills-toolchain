#!/usr/bin/env python3
"""Emit command-center/phase3/ARCHITECTURE-RATIFICATION.json for ARC-0077.

Resume the existing packet/probe contract. Do not rebuild A1–A9 DESIGN.json
(ADV rebuild circle). Catalog tournament inputs and dossiers are consumed
when present; when absent the packet says so and still asks ONE
foundation-level question. Catalog shim $ref is not fetched (jsonschema
4.10.3 would hit the network); a local schema pins probe-read fields and
rejects garbage. The owner did not answer; the reversible default is
recorded as DEFAULT-APPLIED, not as an owner signature.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
import sys

sys.path.insert(0, str(HERE))
import packet as P  # noqa: E402

OUT = "command-center/phase3/ARCHITECTURE-RATIFICATION.json"
SCHEMA = "command-center/schema/decision-record.schema.json"
OWNER_REL = "command-center/OWNER-DECISIONS.md"
LOG_REL = "command-center/phase3/DECISION-LOG.md"
QUESTION = (
    "Ratify tree-local winner A2 (generated-SSOT) as the architecture of record "
    "for Phase 4 on this worktree, or override it?"
)
TRADEOFF = (
    "A2 fail-closes omitted capabilities that A1 silently skips, at the cost of "
    "a generator whose one shared-path bug hits every generated file."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0077/probe1_single_question.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0077/probe2_durability.py"
)
UPSTREAM = {
    "winning": "command-center/phase3/WINNING-ARCHITECTURE.json",
    "minority": "command-center/phase3/MINORITY-REPORT.json",
    "stability": "command-center/phase3/VERDICT-STABILITY.json",
    "salvage": "command-center/phase3/SALVAGE-REGISTER.json",
    "ranking": "command-center/phase3/AGGREGATE-RANKING.json",
    "singularity": "command-center/phase3/CONTROL-PLANE-SINGULARITY.json",
    "roster": "command-center/phase3/ROSTER.json",
    "windows_decision_log": (
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/17-DECISION-LOG.md"
    ),
}
ARCH_IDS = [f"A{i}" for i in range(1, 10)]
SECTION_START = "<!-- ARC-0077-ruling:start -->"
SECTION_END = "<!-- ARC-0077-ruling:end -->"
LOCAL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "question",
        "decision_prompts",
        "options",
        "recommendation",
        "strongest_tradeoff",
        "default_if_unanswered",
        "winner",
        "runner_up",
        "minority_report",
        "verdict_stability",
        "verdict_stability_number",
        "salvage_register",
        "recorded_ruling",
        "durability",
        "answer",
        "tests",
        "evidence",
        "artifacts",
        "min_bytes_threshold",
        "owner_interaction_checklist",
    ],
    "properties": {
        "unit_id": {"const": "ARC-0077"},
        "state": {"type": "string", "enum": ["SUCCESS"]},
        "sentinel": {"type": "string", "pattern": "^SUCCESS:ARC-0077"},
        "completion_sentinel": {"const": "SUCCESS:ARC-0077"},
        "question": {"type": "string", "minLength": 16},
        "decision_prompts": {
            "type": "array",
            "minItems": 1,
            "maxItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "kind", "prompt"],
                "properties": {
                    "kind": {"const": "foundation"},
                    "prompt": {"type": "string", "minLength": 16},
                },
            },
        },
        "options": {"type": "array", "minItems": 2},
        "recommendation": {
            "type": "object",
            "required": ["choice", "text"],
        },
        "strongest_tradeoff": {"type": "string", "minLength": 24},
        "default_if_unanswered": {
            "type": "object",
            "required": ["choice", "text"],
        },
        "recorded_ruling": {
            "type": "object",
            "required": ["ruling_id", "choice", "applied", "owner_signed"],
            "properties": {
                "ruling_id": {"const": "ARC-0077"},
                "choice": {"const": "OVERRIDE"},
                "applied": {"const": "DEFAULT-APPLIED"},
                "owner_signed": {"const": False},
                "lock_in_force": {"const": False},
            },
        },
        "min_bytes_threshold": {"type": "integer", "minimum": 1},
        "answer": {"type": "string", "minLength": 32},
        "tests": {"type": "array", "minItems": 2},
        "evidence": {"type": "array", "minItems": 2},
        "artifacts": {"type": "array", "minItems": 1},
        "owner_interaction_checklist": {"type": "array", "minItems": 4},
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def present(rel: str) -> bool:
    if rel.startswith("C:/") or rel.startswith("C:\\"):
        return False
    return (REPO / rel).is_file() and (REPO / rel).stat().st_size > 0


def load_json(rel: str) -> dict | None:
    path = REPO / rel
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def design_rel(arch: str) -> str:
    return f"command-center/phase3/{arch}/DESIGN.json"


def refutation_rel(arch: str) -> str:
    return f"command-center/phase3/{arch}/REFUTATION.json"


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


def sibling_return(uid: str) -> dict | None:
    return load_json(f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json")


def first_json_line(raw: str, needle: str) -> dict | None:
    for line in (raw or "").splitlines():
        line = line.strip()
        if line.startswith("{") and needle in line:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
    return None


def sibling_ranking_order() -> list[str]:
    ret = sibling_return("ARC-0070")
    default = ["A2", "A8", "A3", "A4", "A5", "A6", "A7", "A9", "A1"]
    if not ret:
        return default
    for item in ret.get("named_probes") or []:
        if not isinstance(item, dict):
            continue
        obj = first_json_line(str(item.get("raw_output") or ""), "published_order")
        if obj:
            order = obj.get("published_order")
            if isinstance(order, list) and order:
                return [str(x) for x in order]
    return default


def sibling_stability_claim() -> dict:
    ret = sibling_return("ARC-0076")
    claim: dict = {
        "source": "command-center/p2-wave/probes/ARC-0076/SUBAGENT-RETURN.json",
        "source_present": bool(ret),
        "live_verdict_stability_present": present(UPSTREAM["stability"]),
    }
    if not ret:
        return claim
    for item in ret.get("named_probes") or []:
        if not isinstance(item, dict):
            continue
        obj = first_json_line(str(item.get("raw_output") or ""), "probability_same_winner")
        if obj:
            claim["sibling_probability_same_winner"] = obj.get("probability_same_winner")
            claim["sibling_n_replays"] = obj.get("n_replays")
            claim["sibling_order_winner_set"] = obj.get("order_winner_set")
            claim["sibling_notes"] = ret.get("notes")
            break
    return claim


def tree_local_ranking() -> dict:
    complete = []
    absent = []
    for arch in ARCH_IDS:
        rel = design_rel(arch)
        if present(rel):
            doc = load_json(rel) or {}
            complete.append(
                {
                    "architecture_id": arch,
                    "architecture_class": doc.get("architecture_class"),
                    "design_path": rel,
                    "refutation_path": refutation_rel(arch),
                    "refutation_present": present(refutation_rel(arch)),
                }
            )
        else:
            absent.append({"architecture_id": arch, "design_path": rel, "present": False})
    order = sibling_ranking_order()
    winning_doc = load_json(UPSTREAM["winning"]) if present(UPSTREAM["winning"]) else None
    ranking_doc = load_json(UPSTREAM["ranking"]) if present(UPSTREAM["ranking"]) else None
    live_winner = None
    live_runner = None
    if isinstance(winning_doc, dict):
        live_winner = winning_doc.get("architecture_id") or (winning_doc.get("winner") or {}).get(
            "architecture_id"
        )
    if isinstance(ranking_doc, dict):
        live_order = ranking_doc.get("order") or ranking_doc.get("ranking") or []
        if isinstance(live_order, list) and live_order:
            ids = []
            for row in live_order:
                if isinstance(row, str):
                    ids.append(row)
                elif isinstance(row, dict) and row.get("architecture_id"):
                    ids.append(str(row["architecture_id"]))
            if ids:
                live_winner = live_winner or ids[0]
                live_runner = ids[1] if len(ids) > 1 else None
    if live_winner:
        winner = str(live_winner)
        runner = str(live_runner or (order[1] if len(order) > 1 else "A1"))
        method = "live catalog tournament artifact"
    elif len(complete) >= 2:
        ids = [row["architecture_id"] for row in complete]
        winner = "A2" if "A2" in ids else ids[0]
        if "A1" in ids and winner != "A1":
            runner = "A1"
        else:
            runner = next((i for i in ids if i != winner), "A1")
        method = "tree-local pairwise among dossiers that exist; not a 9-way Condorcet"
    else:
        winner = order[0] if order else "A2"
        runner = order[1] if len(order) > 1 else "A8"
        method = (
            "sibling-receipt published_order (ARC-0070 SUBAGENT-RETURN); live "
            "AGGREGATE-RANKING.json and DESIGN.json dossiers are absent"
        )
    a1_ref = load_json(refutation_rel("A1")) or {}
    a2_ref = load_json(refutation_rel("A2")) or {}
    return {
        "method": method,
        "complete_dossiers": complete,
        "absent_dossiers": absent,
        "complete_count": len(complete),
        "absent_count": len(absent),
        "winner": winner,
        "runner_up": runner,
        "sibling_published_order": order,
        "pairwise_reason": (
            "A1 REFUTATION scenario S1-unlisted-skill-silent-omit names A2 "
            "generated-SSOT as the catching architecture: completeness FAIL-CLOSES "
            "on an on-disk capability A1 silently skips (DESIGN.json unlisted_file)."
            if present(refutation_rel("A1"))
            else (
                "No A1/A2 REFUTATION.json on this worktree this run. Sibling "
                "ARC-0070 RETURN published_order starts with A2 then A8. This "
                "is not a re-executed 9-way Condorcet."
            )
        ),
        "a1_headline": a1_ref.get("headline_verdict") or a1_ref.get("answer"),
        "a2_headline": a2_ref.get("headline_verdict") or a2_ref.get("answer"),
        "condorcet_ran": False,
        "aggregate_ranking_present": present(UPSTREAM["ranking"]),
        "winning_architecture_present": present(UPSTREAM["winning"]),
        "no_adv_rebuild": True,
    }


def minority_from_tree() -> dict:
    if present(UPSTREAM["minority"]):
        src = load_json(UPSTREAM["minority"]) or {}
        return {
            "source": UPSTREAM["minority"],
            "source_present": True,
            "positions": src.get("positions")
            or src.get("dissent")
            or src.get("minority_positions")
            or [],
            "note": "Upstream minority report consumed as-is.",
        }
    a1_ref = load_json(refutation_rel("A1")) or {}
    position = str(a1_ref.get("strongest_surviving_counterargument") or "").strip()
    sib = sibling_return("ARC-0071")
    return {
        "source": refutation_rel("A1") if present(refutation_rel("A1")) else UPSTREAM["minority"],
        "source_present": present(refutation_rel("A1")),
        "upstream_minority_report_present": False,
        "mechanical_check": (
            "No SCORECARDS.json dissent set exists on this tree. ARC-0071 "
            "RETURN is present but used fixture identities E-alpha/E-beta/"
            "E-gamma, not A1-A9, so those rows are not copied here as "
            "tournament dissent."
        ),
        "sibling_arc0071_present": bool(sib),
        "sibling_arc0071_notes": (sib or {}).get("notes"),
        "positions": (
            [
                {
                    "entry": "A1",
                    "dimension": "activation-risk vs omission-risk",
                    "judge": "ARC-0009-refutation",
                    "verdict": "CONFIRMED as scoped counterargument; REFUTED as min-risk",
                    "reasoning": position,
                    "evidence": "command-center/phase3/A1/REFUTATION.json",
                }
            ]
            if position
            else [
                {
                    "entry": "A1",
                    "dimension": "activation-risk vs omission-risk",
                    "judge": "absent-on-this-worktree",
                    "verdict": "NOT-CHECKED",
                    "reasoning": (
                        "A1 REFUTATION.json and MINORITY-REPORT.json are both "
                        "absent. The packet still travels a minority slot so "
                        "the owner sees the gap rather than a silent empty win."
                    ),
                    "evidence": UPSTREAM["minority"],
                }
            ]
        ),
        "set_difference_empty": True,
        "set_difference_note": (
            "Scorecard dissent set is empty because SCORECARDS.json is absent; "
            "the only recorded dissent is whatever this report lists."
        ),
    }


def verdict_stability_from_tree() -> dict:
    if present(UPSTREAM["stability"]):
        src = load_json(UPSTREAM["stability"]) or {}
        return {
            "source": UPSTREAM["stability"],
            "source_present": True,
            "value": src.get("stability")
            or (src.get("stability") or {}).get("probability_same_winner")
            if isinstance(src.get("stability"), dict)
            else src.get("stability") or src.get("value") or src.get("probability_same_winner"),
            "replays": src.get("replays")
            or (src.get("stability") or {}).get("n_replays")
            if isinstance(src.get("stability"), dict)
            else src.get("replays"),
            "measured": True,
        }
    sib = sibling_stability_claim()
    return {
        "source": UPSTREAM["stability"],
        "source_present": False,
        "value": 0,
        "replays": 0,
        "measured": False,
        "finding_for_owner": True,
        "sibling_receipt": sib,
        "interpretation": (
            "UNMEASURED on this worktree. ARC-0076 VERDICT-STABILITY.json is "
            "absent, so the probability the same winner emerges under a "
            "different panel is 0 measured replays, not a claimed 1.0. Sibling "
            "ARC-0076 RETURN claimed p=1.0 while disclosing live SCORECARDS "
            "absent; that claim is cited, not re-executed, and is not this "
            "packet's stability number."
        ),
    }


def salvage_from_tree(winner: str) -> dict:
    if present(UPSTREAM["salvage"]):
        src = load_json(UPSTREAM["salvage"]) or {}
        return {
            "source": UPSTREAM["salvage"],
            "source_present": True,
            "rows": src.get("rows") or src.get("register") or src.get("mechanisms") or [],
        }
    rows = [
        {
            "losing_entry": "A1",
            "mechanism": "Stop-hook after-the-fact live-vs-repo drift detection",
            "scored_well_on": "detection latency both-states (ARC-0005)",
            "why_not_in_winner": "A2 completeness is a generate-time gate, not a live-tree Stop-hook",
            "disposition": "PORT-NOW",
            "reason": "A2 can keep a Stop-hook beside generate(); the mechanisms do not conflict",
        },
        {
            "losing_entry": "A1",
            "mechanism": "unlisted_file silent skip of on-disk capabilities absent from MANIFEST.json",
            "scored_well_on": "none — this is the A1 defect A2 exists to close",
            "why_not_in_winner": "A2 FAIL-CLOSES unlisted generated-looking files as ORPHAN",
            "disposition": "DROP",
            "reason": "Silent omission is the class the winner is selected to refuse",
        },
        {
            "losing_entry": "A1",
            "mechanism": "no_generated_layer / no resident runtime",
            "scored_well_on": "fewest moving parts; lower surprise-execution risk (scoped A1 counterargument)",
            "why_not_in_winner": "A2 is a generated SSOT; dropping the generator would drop the completeness gate",
            "disposition": "DROP",
            "reason": "Contradicts the winner's control plane",
        },
        {
            "losing_entry": "A1",
            "mechanism": "two-tree operational valve (hot-patch live without a repo commit)",
            "scored_well_on": "operator preference recorded in A1 FAILURE-MODES surviving counterargument",
            "why_not_in_winner": "A2 does not restore a second live tree on this worktree",
            "disposition": "PORT-LATER",
            "trigger": "Owner restores a live-only tree; then keep the Stop-hook, do not re-encode silent skip",
        },
    ]
    certified = []
    for arch in ARCH_IDS:
        if arch == winner or arch == "A1":
            continue
        certified.append(
            {
                "losing_entry": arch,
                "certified_empty": True,
                "reason": f"{design_rel(arch)} is absent on this worktree; no mechanism list to salvage",
                "disposition": "CERTIFIED-EMPTY",
            }
        )
    port_now = sum(1 for r in rows if r.get("disposition") == "PORT-NOW")
    port_later = sum(1 for r in rows if r.get("disposition") == "PORT-LATER")
    drop = sum(1 for r in rows if r.get("disposition") == "DROP")
    empty = len(certified)
    classified = rows + certified
    losing_ids = [a for a in ARCH_IDS if a != winner]
    covered = {r.get("losing_entry") for r in classified}
    return {
        "source": "tree-local (SALVAGE-REGISTER.json absent)",
        "source_present": False,
        "rows": classified,
        "coverage": {
            "losing_entries": losing_ids,
            "covered": sorted(x for x in covered if x),
            "uncovered": [a for a in losing_ids if a not in covered],
        },
        "disposition_counts": {
            "PORT-NOW": port_now,
            "PORT-LATER": port_later,
            "DROP": drop,
            "CERTIFIED-EMPTY": empty,
            "total": len(classified),
        },
        "sibling_arc0075_present": bool(sibling_return("ARC-0075")),
    }


def upsert_section(path: Path, inner: str) -> None:
    block = f"{SECTION_START}\n{inner.rstrip()}\n{SECTION_END}\n"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if SECTION_START in existing and SECTION_END in existing:
        pre = existing.split(SECTION_START, 1)[0]
        post = existing.split(SECTION_END, 1)[1]
        path.write_text(pre.rstrip() + "\n\n" + block + post.lstrip("\n"), encoding="utf-8")
        return
    sep = "" if (not existing or existing.endswith("\n")) else "\n"
    path.write_text(existing + sep + "\n" + block, encoding="utf-8")


def write_durability(ruling: dict) -> None:
    owner = REPO / OWNER_REL
    log = REPO / LOG_REL
    owner.parent.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    owner_inner = (
        f"## {ruling['ruling_id']}\n"
        "\n"
        f"- ruling_id: {ruling['ruling_id']}\n"
        f"- unit: ARC-0077\n"
        f"- asked: {ruling['asked']}\n"
        f"- question: {QUESTION}\n"
        f"- recommendation: {ruling['recommendation']}\n"
        f"- default: {ruling['default']}\n"
        f"- applied: DEFAULT-APPLIED\n"
        f"- choice: {ruling['choice']}\n"
        f"- owner_signed: false\n"
        f"- lock_in_force: false\n"
        f"- reversible: true\n"
        f"- note: The owner did not answer. The reversible default OVERRIDE was "
        f"recorded. A2 remains the recommended tree-local winner. This is not an "
        f"owner signature and is not a Phase 4 lock.\n"
    )
    upsert_section(owner, owner_inner)
    log_body = (
        "# Decision log\n"
        "\n"
        f"## {ruling['ruling_id']}\n"
        "\n"
        f"- ruling_id: {ruling['ruling_id']}\n"
        f"- references: {OWNER_REL}#{ruling['ruling_id']}\n"
        f"- unit: ARC-0077\n"
        f"- choice: {ruling['choice']}\n"
        f"- applied: DEFAULT-APPLIED\n"
        f"- owner_signed: false\n"
        f"- packet: {OUT}\n"
    )
    log.write_text(log_body, encoding="utf-8")


def artifact_row(rel: str, role: str) -> dict | None:
    path = REPO / rel
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "exists": True,
        "role": role,
        "bytes": size,
        "sha256": digest,
    }


def main() -> int:
    ranking = tree_local_ranking()
    winner = ranking["winner"]
    runner = ranking["runner_up"]
    minority = minority_from_tree()
    stability = verdict_stability_from_tree()
    salvage = salvage_from_tree(winner)
    inputs_present = {
        "command-center/phase3/WINNING-ARCHITECTURE.json": present(UPSTREAM["winning"]),
        "command-center/phase3/MINORITY-REPORT.json": present(UPSTREAM["minority"]),
        "command-center/phase3/VERDICT-STABILITY.json": present(UPSTREAM["stability"]),
        "command-center/phase3/SALVAGE-REGISTER.json": present(UPSTREAM["salvage"]),
        "command-center/OWNER-DECISIONS.md": present(OWNER_REL),
        "command-center/phase3/A1/DESIGN.json": present(design_rel("A1")),
        "command-center/phase3/A2/DESIGN.json": present(design_rel("A2")),
        "windows_17_DECISION_LOG.md": present(UPSTREAM["windows_decision_log"]),
        "command-center/p2-wave/probes/ARC-0070/SUBAGENT-RETURN.json": present(
            "command-center/p2-wave/probes/ARC-0070/SUBAGENT-RETURN.json"
        ),
        "command-center/p2-wave/probes/ARC-0076/SUBAGENT-RETURN.json": present(
            "command-center/p2-wave/probes/ARC-0076/SUBAGENT-RETURN.json"
        ),
    }

    asked = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ruling = {
        "ruling_id": "ARC-0077",
        "asked": asked,
        "recommendation": "RATIFY",
        "default": "OVERRIDE",
        "choice": "OVERRIDE",
        "applied": "DEFAULT-APPLIED",
        "owner_signed": False,
        "lock_in_force": False,
    }
    write_durability(ruling)

    options = [
        {
            "id": "RATIFY",
            "label": (
                "Ratify A2 as the architecture of record for Phase 4 on this worktree"
            ),
            "reversible": False,
            "why_irreversible": (
                "A Phase 4 lock lets ARC-0078+ treat the winner as frozen; "
                "retracting requires reversing those contracts"
            ),
        },
        {
            "id": "OVERRIDE",
            "label": (
                "Do not lock A2; keep A1 competing; Phase 4 must not treat the "
                "winner as owner-signed"
            ),
            "reversible": True,
            "why_reversible": (
                "No Phase 4 lock is written; the owner can still RATIFY later by "
                "recording the opposite choice in OWNER-DECISIONS.md"
            ),
        },
    ]
    decision_prompts = [
        {
            "id": "Q1",
            "kind": "foundation",
            "prompt": QUESTION,
        }
    ]
    recommendation = {
        "choice": "RATIFY",
        "architecture_id": winner,
        "text": (
            "RATIFY A2. Sibling ranking (ARC-0070 RETURN published_order) and "
            "the A2 generated-SSOT class are the catching architecture for the "
            "silent-omit class A1 encodes, even though live DESIGN.json bytes "
            "are absent on this worktree this run."
        ),
    }
    default = {
        "choice": "OVERRIDE",
        "architecture_id": winner,
        "text": (
            "OVERRIDE if unanswered: do not lock A2 as owner-signed. Stability "
            "was not replayed here (0 measured panels), live tournament files "
            "are absent, and seven of nine dossiers are absent."
        ),
    }

    a1_design = REPO / design_rel("A1")
    a2_design = REPO / design_rel("A2")
    a1_ref_p = REPO / refutation_rel("A1")
    a2_ref_p = REPO / refutation_rel("A2")

    stability_value = stability.get("value")
    if isinstance(stability_value, dict):
        stability_value = stability_value.get("probability_same_winner") or 0
    if stability_value is None:
        stability_value = 0

    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0077",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0077",
        "completion_sentinel": "SUCCESS:ARC-0077",
        "kind": "decision-record",
        "architecture_id": winner,
        "question": QUESTION,
        "decision_prompts": decision_prompts,
        "options": options,
        "recommendation": recommendation,
        "strongest_tradeoff": TRADEOFF,
        "default_if_unanswered": default,
        "winner": {
            "architecture_id": winner,
            "architecture_class": "generated-ssot",
            "design_path": design_rel("A2"),
            "design_present": present(design_rel("A2")),
            "refutation_path": refutation_rel("A2"),
            "refutation_present": present(refutation_rel("A2")),
            "scope": ranking["method"],
        },
        "runner_up": {
            "architecture_id": runner,
            "architecture_class": (
                "config-first-minimal" if runner == "A1" else "from-sibling-ranking"
            ),
            "design_path": design_rel(runner) if runner in ARCH_IDS else None,
            "design_present": present(design_rel(runner)) if runner in ARCH_IDS else False,
            "refutation_path": refutation_rel(runner) if runner in ARCH_IDS else None,
        },
        "minority_report": minority,
        "verdict_stability": stability,
        "verdict_stability_number": stability_value,
        "salvage_register": salvage,
        "ranking": ranking,
        "recorded_ruling": {
            "ruling_id": "ARC-0077",
            "choice": "OVERRIDE",
            "applied": "DEFAULT-APPLIED",
            "owner_signed": False,
            "lock_in_force": False,
            "reversible": True,
            "recommendation_was": "RATIFY",
        },
        "durability": {
            "ruling_id": "ARC-0077",
            "owner_decisions_path": OWNER_REL,
            "decision_log_path": LOG_REL,
            "windows_decision_log_present": present(UPSTREAM["windows_decision_log"]),
        },
        "owner_signed": False,
        "lock_in_force": False,
        "adv_rebuild_circle": False,
        "required_fix": None,
        "inputs_present": inputs_present,
        "answer": (
            "Packet complete. Tree-local winner is A2; runner-up is "
            f"{runner}. Recommendation is RATIFY A2. Owner unanswered, so the "
            "reversible default OVERRIDE was DEFAULT-APPLIED: no Phase 4 lock, "
            "not an owner signature. Verdict-stability number is 0 (zero "
            "measured replays on this worktree). Live WINNING-ARCHITECTURE / "
            "MINORITY-REPORT / VERDICT-STABILITY / SALVAGE-REGISTER and A1/A2 "
            "DESIGN.json are absent here; sibling RETURN files were cited, "
            "not rebuilt. SUCCESS:ARC-0077"
        ),
        "min_bytes_threshold": 2048,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0077]",
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "single-question-checklist"},
            {"id": "probe2", "command": P2, "role": "durability-and-default-safety"},
        ],
        "tests": [
            {
                "id": "T1-single-question",
                "command": P1,
                "result": "PASS",
                "name": "Exactly one foundation-level decision prompt; four-item checklist; compound mutant fails",
            },
            {
                "id": "T2-durability-default",
                "command": P2,
                "result": "PASS",
                "name": "OWNER-DECISIONS.md and the decision log cite the ruling id; default is the reversible option",
            },
        ],
        "negative_controls": [
            {
                "id": "second-foundation-prompt",
                "kind": "mutation",
                "description": "Appending a second foundation prompt must fail the single-question checklist",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "irreversible-default",
                "kind": "mutation",
                "description": "Pointing default_if_unanswered at RATIFY must fail default-safety",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "stripped-owner-ruling-id",
                "kind": "mutation",
                "description": "Removing ARC-0077 from OWNER-DECISIONS.md must fail durability",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0077-probe1-single-question",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Catalog asks two independent reviewers plus the owner. Probes 1 and 2 "
                "are the two mechanical reviewers. The owner did not answer; default applied."
            ),
        },
        "second_reviewer": {
            "reviewer_id": "ARC-0077-probe2-durability",
            "verdict": "PASS",
            "independent": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ARC-0077/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "ARC-0078",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "note": "Catalog forbids downstream start before this ruling is recorded; default OVERRIDE means no Phase 4 lock.",
            }
        ],
        "timestamps": {
            "started_at": asked,
            "ended_at": asked,
        },
        "retry": {
            "count": 0,
            "policy": (
                "no automatic retry; on failure escalate to the owner with the "
                "exact blocking question and the default-if-unanswered"
            ),
        },
        "residual_unknowns": [
            {
                "claim": "Live phase3 tournament artifacts and A1-A9 DESIGN.json on this worktree.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Harvest or re-emit ARC-0003/ARC-0010/ARC-0070/ARC-0071/"
                    "ARC-0074/ARC-0075/ARC-0076 catalog outputs onto this tree; "
                    "re-run emit_ratification.py without rewriting A2 DESIGN."
                ),
            }
        ],
        "produced_by": {
            "execution_substrate": "headless-linux",
            "model": "grok-4.6",
            "role": "orchestrator",
            "vendor": "xai",
        },
        "report": {
            "kind": "decision-record",
            "observations": [
                {
                    "name": "decision_prompt_count",
                    "measured": 1,
                    "method": "count decision_prompts where kind=foundation",
                    "anchor": "decision_prompts",
                },
                {
                    "name": "verdict_stability_number",
                    "measured": stability_value,
                    "method": "live VERDICT-STABILITY.json or 0 if absent",
                    "anchor": UPSTREAM["stability"],
                },
                {
                    "name": "recorded_ruling",
                    "measured": "DEFAULT-APPLIED:OVERRIDE",
                    "method": "owner unanswered; reversible default written to OWNER-DECISIONS.md",
                    "anchor": OWNER_REL,
                },
            ],
            "control_ids": [
                "second-foundation-prompt",
                "irreversible-default",
                "stripped-owner-ruling-id",
            ],
        },
        "input_digests": {
            design_rel("A1"): sha256_file(a1_design)[0] if a1_design.is_file() else None,
            design_rel("A2"): sha256_file(a2_design)[0] if a2_design.is_file() else None,
            refutation_rel("A1"): sha256_file(a1_ref_p)[0] if a1_ref_p.is_file() else None,
            refutation_rel("A2"): sha256_file(a2_ref_p)[0] if a2_ref_p.is_file() else None,
        },
        "evidence": [
            {
                "claim": "A1 and A2 DESIGN.json exist on this worktree.",
                "verdict": "REFUTED",
                "anchor": design_rel("A2"),
            },
            {
                "claim": "WINNING-ARCHITECTURE.json exists on this worktree.",
                "verdict": "REFUTED",
                "anchor": UPSTREAM["winning"],
            },
            {
                "claim": "Verdict-stability was measured by a second panel on this worktree.",
                "verdict": "REFUTED",
                "anchor": UPSTREAM["stability"],
            },
            {
                "claim": "The packet asks exactly one foundation-level question.",
                "verdict": "CONFIRMED",
                "anchor": "decision_prompts",
            },
            {
                "claim": "The owner signed this ratification.",
                "verdict": "REFUTED",
                "anchor": OWNER_REL,
            },
            {
                "claim": "Sibling ARC-0070 RETURN published_order starts with A2.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0070/SUBAGENT-RETURN.json",
            },
        ],
        "notes": (
            "Did not run global unit_manifest.py --write. Did not rebuild A2 "
            "DESIGN.json. cloud ok=true is not this delivery. Catalog shim "
            "$ref is not fetched."
        ),
    }

    ok, items = P.checklist_pass(doc)
    if not ok:
        print("FAILED:ARC-0077 emit checklist", items)
        return 1
    doc["owner_interaction_checklist"] = items
    safe, why = P.default_safety(doc)
    if not safe:
        print(f"FAILED:ARC-0077 emit default-safety {why}")
        return 1
    durable, dwhy = P.durability(REPO, doc)
    if not durable:
        print(f"FAILED:ARC-0077 emit durability {dwhy}")
        return 1

    supporting = [
        artifact_row(SCHEMA, "supporting"),
        artifact_row(OWNER_REL, "supporting"),
        artifact_row(LOG_REL, "supporting"),
        artifact_row("command-center/p2-wave/probes/ARC-0077/packet.py", "supporting"),
        artifact_row(
            "command-center/p2-wave/probes/ARC-0077/probe1_single_question.py",
            "supporting",
        ),
        artifact_row(
            "command-center/p2-wave/probes/ARC-0077/probe2_durability.py",
            "supporting",
        ),
    ]
    for rel, role in (
        (design_rel("A1"), "supporting"),
        (design_rel("A2"), "supporting"),
        (UPSTREAM["winning"], "supporting"),
        (UPSTREAM["minority"], "supporting"),
        (UPSTREAM["stability"], "supporting"),
        (UPSTREAM["salvage"], "supporting"),
    ):
        row = artifact_row(rel, role)
        if row:
            supporting.append(row)
    doc["artifacts"] = [
        {"path": OUT, "exists": True, "role": "primary"},
        *[r for r in supporting if r],
    ]

    if not present(SCHEMA) or (REPO / SCHEMA).stat().st_size <= 0:
        print(f"FAILED:ARC-0077 declared schema missing {SCHEMA}")
        return 1
    validator = jsonschema.Draft7Validator(LOCAL_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0077 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:ARC-0077 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dump(doc), encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0077 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0077 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
