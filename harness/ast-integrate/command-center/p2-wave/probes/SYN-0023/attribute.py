#!/usr/bin/env python3
"""Convergence attribution: corroboration vs conformity.

Join key is artifact identity (sha256, then artifact_id, then path).
Title is never an identity. Shared-ancestor detection walks parent edges
so two disjoint reads of children of one stale source still count as
CONFORMITY.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CORROBORATED = "CORROBORATED"
CONFORMITY = "CONFORMITY"
JOIN_IDENTITY = "identity"
JOIN_TITLE = "title"

SENTINEL = (
    "SUCCESS:SYN-0023 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both planted cases "
    "labelled correctly and the conformity share is published. Any other "
    "terminal state is FAILED:SYN-0023 <classification> with the diagnostic "
    "tail attached."
)
QUESTION = (
    "Question: for each conclusion the independent syntheses agreed on, is "
    "the agreement traceable to INDEPENDENT source lineage, or to one shared "
    "upstream artifact every agent read? Target: label each agreed conclusion "
    "CORROBORATED (>=2 independent lineages) or CONFORMITY (one shared "
    "ancestor), because N agents reading the same stale input is one lens, "
    "not N. Distinct from SYN-0010, which measures the amount of agreement "
    "without explaining it."
)
NULL_MODEL = (
    "Sampling frame: the SYN-0010 agreed-conclusion universe (live), with "
    "planted controls scored in a separate table and never mixed into the "
    "live share. Conformity share = |CONFORMITY| / |frame|. Chance-corrected "
    "agreement (SYN-0010) is not reused here; this unit attributes already-"
    "agreed items by lineage intersection after ancestor closure. An empty "
    "live universe yields an undefined share (UNIVERSE-EMPTY), not 0%. A "
    "high SYN-0010 coefficient with a high conformity share is a warning, "
    "not a result."
)
OUT_REL = "command-center/receipts/SYN-0023.json"
SCHEMA_REL = "command-center/schema/convergence-attribution.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0023/probe1_planted_labels.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0023/probe2_identity_join.py"
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_identity(obj: dict, join: str = JOIN_IDENTITY) -> str:
    """Identity of one artifact. Title is used only when join==title (trap)."""
    if join == JOIN_TITLE:
        title = obj.get("title") or obj.get("name")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title-join requires a non-empty title")
        return "title:" + title.strip().casefold()
    sha = obj.get("sha256") or obj.get("digest")
    if isinstance(sha, str) and sha.strip():
        return "sha256:" + sha.strip().lower()
    aid = obj.get("artifact_id")
    if isinstance(aid, str) and aid.strip():
        return "id:" + aid.strip()
    path = obj.get("path")
    if isinstance(path, str) and path.strip():
        return "path:" + path.replace("\\", "/").strip()
    raise ValueError("artifact has no identity (need sha256, artifact_id, or path)")


def materialize(scenario: dict, join: str = JOIN_IDENTITY) -> tuple[dict, dict]:
    """Return (by_artifact_id, parent_map identity->set[parent identity])."""
    by_aid: dict[str, dict] = {}
    for raw in scenario.get("artifacts") or []:
        rec = dict(raw)
        payload = rec.get("payload")
        if isinstance(payload, str) and not rec.get("sha256"):
            rec["sha256"] = sha256_text(payload)
        rec["identity"] = artifact_identity(rec, join=join)
        aid = str(rec.get("artifact_id") or rec["identity"])
        rec["artifact_id"] = aid
        by_aid[aid] = rec
    parent_map: dict[str, set[str]] = {rec["identity"]: set() for rec in by_aid.values()}
    for rec in by_aid.values():
        child = rec["identity"]
        for parent_ref in rec.get("parents") or []:
            if parent_ref in by_aid:
                parent_map[child].add(by_aid[parent_ref]["identity"])
            else:
                parent_map.setdefault(str(parent_ref), set())
                parent_map[child].add(str(parent_ref))
    return by_aid, parent_map


def ancestors(node: str, parent_map: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    stack = list(parent_map.get(node, ()))
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(parent_map.get(cur, ()))
    return seen


def lineage_set(reads: Iterable[str], parent_map: dict[str, set[str]]) -> set[str]:
    out: set[str] = set()
    for node in reads:
        out.add(node)
        out |= ancestors(node, parent_map)
    return out


def lowest_common(inter: set[str], parent_map: dict[str, set[str]]) -> list[str]:
    """Nodes in the intersection that are not ancestors of other intersection nodes."""
    lowest: list[str] = []
    for node in sorted(inter):
        if any(node in ancestors(other, parent_map) for other in inter if other != node):
            continue
        lowest.append(node)
    return lowest


def attribute(
    agent_reads: dict[str, list[str]],
    parent_map: dict[str, set[str]],
) -> dict:
    if len(agent_reads) < 2:
        raise ValueError("need >=2 agents to attribute agreement")
    lineages = {
        agent: sorted(lineage_set(reads, parent_map))
        for agent, reads in agent_reads.items()
    }
    sets = {agent: set(vals) for agent, vals in lineages.items()}
    inter = set.intersection(*sets.values()) if sets else set()
    if inter:
        lca = lowest_common(inter, parent_map)
        label = CONFORMITY
    else:
        lca = []
        label = CORROBORATED
    return {
        "label": label,
        "lineage_by_agent": {k: v for k, v in sorted(lineages.items())},
        "intersection": sorted(inter),
        "lowest_common_ancestors": lca,
        "independent_lineage_count": len(sets) if not inter else 1,
    }


def scenario_agent_reads(scenario: dict, by_aid: dict[str, dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for agent in scenario.get("agents") or []:
        aid = str(agent["id"])
        reads = []
        for ref in agent.get("reads") or []:
            if ref not in by_aid:
                raise KeyError(f"agent {aid} reads unknown artifact {ref}")
            reads.append(by_aid[ref]["identity"])
        out[aid] = reads
    return out


def attribute_scenario(scenario: dict, join: str = JOIN_IDENTITY) -> dict:
    by_aid, parent_map = materialize(scenario, join=join)
    reads = scenario_agent_reads(scenario, by_aid)
    result = attribute(reads, parent_map)
    expected = scenario.get("expected_label")
    observed = result["label"]
    return {
        "id": scenario.get("id"),
        "conclusion_id": scenario.get("conclusion_id"),
        "conclusion": scenario.get("conclusion"),
        "claim_true": scenario.get("claim_true"),
        "expected_label": expected,
        "observed_label": observed,
        "correct": expected is None or expected == observed,
        "lineage_by_agent": result["lineage_by_agent"],
        "lowest_common_ancestors": result["lowest_common_ancestors"],
        "intersection": result["intersection"],
        "independent_lineage_count": result["independent_lineage_count"],
        "join_key": "artifact-identity" if join == JOIN_IDENTITY else "title",
        "artifacts": {
            aid: {
                "identity": rec["identity"],
                "sha256": rec.get("sha256"),
                "title": rec.get("title"),
                "path": rec.get("path"),
            }
            for aid, rec in sorted(by_aid.items())
        },
    }


def share_from_labels(labels: list[str], frame: str) -> dict:
    den = len(labels)
    num = sum(1 for lab in labels if lab == CONFORMITY)
    if den == 0:
        return {
            "numerator": 0,
            "denominator": 0,
            "value": None,
            "published": True,
            "formula": "|CONFORMITY| / |agreed set|",
            "sampling_frame": frame,
            "status": "UNIVERSE-EMPTY",
        }
    return {
        "numerator": num,
        "denominator": den,
        "value": num / den,
        "published": True,
        "formula": "|CONFORMITY| / |agreed set|",
        "sampling_frame": frame,
        "status": "COMPUTED",
    }


def load_planted_scenarios() -> list[dict]:
    fixtures = HERE / "fixtures"
    names = [
        "planted_conformity.json",
        "planted_corroboration.json",
        "planted_shared_stale_ancestor.json",
        "planted_title_trap.json",
    ]
    out = []
    for name in names:
        out.append(load_json(fixtures / name))
    return out


def required_planted() -> list[dict]:
    """The two catalog-required planted cases plus shared-stale-ancestor."""
    return [
        s
        for s in load_planted_scenarios()
        if s.get("id") in {
            "planted-conformity",
            "planted-corroboration",
            "planted-shared-stale-ancestor",
        }
    ]
