#!/usr/bin/env python3
"""Executable fusion lineage: fuse, decompose, execute, license audit.

This is the confirmer's independent oracle for CNF-0176. Decomposition is a
true inverse of union-fusion under a structural fingerprint. Execution runs
named ops to a terminal state; parsing JSON is not enough.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

MORE_STAGES_REFUSAL = "11170-more-stages-without-capability"
LOST_CAPABILITY = "11332-lost-capability"
LOST_PROVENANCE = "11334-lost-provenance-or-license"


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_text(text: str) -> str:
    return digest_bytes(text.encode("utf-8"))


def structural_fingerprint(workflow: dict) -> str:
    lineage = workflow.get("lineage") or {}
    payload = {
        "id": workflow.get("id"),
        "strategy": lineage.get("strategy"),
        "capabilities": sorted(workflow.get("capabilities") or []),
        "stages": [
            {
                "id": s.get("id"),
                "kind": s.get("kind"),
                "capabilities": sorted(s.get("capabilities") or []),
                "source_id": s.get("source_id"),
            }
            for s in (workflow.get("stages") or [])
        ],
        "sources": sorted(
            [
                {
                    "id": src.get("id"),
                    "license": src.get("license") or "",
                    "credit": src.get("credit") or "",
                    "version": src.get("version") or "",
                }
                for src in (lineage.get("sources") or [])
            ],
            key=lambda x: str(x.get("id") or ""),
        ),
    }
    return digest_text(canonical(payload))


def op_tokenize(ctx: dict) -> dict:
    text = str(ctx.get("text") or "")
    tokens = [t for t in re.split(r"\s+", text.strip()) if t]
    out = dict(ctx)
    out["tokens"] = tokens
    out["state"] = "ok"
    return out


def op_normalize(ctx: dict) -> dict:
    cleaned = []
    for tok in ctx.get("tokens") or []:
        t = re.sub(r"[^a-z0-9]+", "", str(tok).lower())
        if t:
            cleaned.append(t)
    out = dict(ctx)
    out["tokens"] = cleaned
    out["state"] = "ok"
    return out


def op_rank(ctx: dict) -> dict:
    tokens = sorted(ctx.get("tokens") or [], key=lambda t: (-len(str(t)), str(t)))
    out = dict(ctx)
    out["tokens"] = tokens
    out["state"] = "ok"
    return out


def op_filter(ctx: dict) -> dict:
    min_len = int(ctx.get("min_len") or 3)
    tokens = [t for t in (ctx.get("tokens") or []) if len(str(t)) >= min_len]
    out = dict(ctx)
    out["tokens"] = tokens
    out["state"] = "ok"
    return out


OPS = {
    "tokenize": op_tokenize,
    "normalize": op_normalize,
    "rank": op_rank,
    "filter": op_filter,
}


def execute(workflow: dict, case: dict) -> dict:
    """Run every stage. Unknown ops fail closed; parse-only is not a terminal ok."""
    stages = list(workflow.get("stages") or [])
    if not stages:
        return {
            "state": "error",
            "reason": "no-stages",
            "terminal": False,
            "stages_run": [],
            "output": dict(case),
            "executed": False,
        }
    ctx = dict(case)
    ctx["state"] = "running"
    ran: list[str] = []
    for st in stages:
        kind = str(st.get("kind") or "")
        op = OPS.get(kind)
        if op is None:
            return {
                "state": "error",
                "reason": f"unknown-op:{kind}",
                "terminal": False,
                "stages_run": ran,
                "output": ctx,
                "executed": False,
            }
        ctx = op(ctx)
        ran.append(str(st.get("id") or kind))
        if ctx.get("state") == "error":
            return {
                "state": "error",
                "reason": str(ctx.get("reason") or "op-error"),
                "terminal": False,
                "stages_run": ran,
                "output": ctx,
                "executed": False,
            }
    ctx["state"] = "ok"
    return {
        "state": "ok",
        "reason": "",
        "terminal": True,
        "stages_run": ran,
        "output": ctx,
        "executed": True,
        "tokens": list(ctx.get("tokens") or []),
    }


def capability_set(workflow: dict) -> set[str]:
    caps = set(workflow.get("capabilities") or [])
    for st in workflow.get("stages") or []:
        caps.update(st.get("capabilities") or [])
    return {str(c) for c in caps if c}


def capability_losses(fusion: dict, sources: list[dict]) -> list[dict]:
    fusion_caps = capability_set(fusion)
    losses = []
    for src in sources:
        missing = sorted(capability_set(src) - fusion_caps)
        if missing:
            losses.append(
                {
                    "source_id": src.get("id"),
                    "lost_capabilities": missing,
                    "defect": LOST_CAPABILITY,
                }
            )
    return losses


def fusion_accept_gate(candidate: dict, sources: list[dict]) -> dict:
    """11170: more stages alone is not acceptance; need complementary capability."""
    fusion_caps = capability_set(candidate)
    source_caps = [capability_set(s) for s in sources]
    more_stages = len(candidate.get("stages") or []) > max(
        (len(s.get("stages") or []) for s in sources), default=0
    )
    strictly_more = any(fusion_caps > sc for sc in source_caps) if source_caps else False
    if more_stages and not strictly_more:
        return {
            "accepted": False,
            "reason": MORE_STAGES_REFUSAL,
            "more_stages": True,
            "strictly_more_capability": False,
        }
    return {
        "accepted": True,
        "reason": "complementary-capability" if strictly_more else "not-merely-larger",
        "more_stages": more_stages,
        "strictly_more_capability": strictly_more,
    }


def fuse_union(sources: list[dict], fusion_id: str) -> dict:
    if len(sources) < 2:
        raise ValueError("union fusion requires at least two sources")
    stages = []
    caps: set[str] = set()
    lineage_sources = []
    for src in sources:
        caps.update(capability_set(src))
        license_id = str(src.get("license") or "")
        credit = str(src.get("credit") or "")
        lineage_sources.append(
            {
                "id": src["id"],
                "version": src.get("version") or "1.0.0",
                "license": license_id,
                "spdx": src.get("spdx") or license_id,
                "credit": credit,
            }
        )
        for st in src.get("stages") or []:
            stamped = dict(st)
            stamped["source_id"] = src["id"]
            stamped["source_license"] = license_id
            stamped["source_credit"] = credit
            stages.append(stamped)
    fusion = {
        "id": fusion_id,
        "kind": "fused-workflow",
        "capabilities": sorted(caps),
        "stages": stages,
        "lineage": {
            "strategy": "union",
            "sources": lineage_sources,
            "decomposable": True,
        },
    }
    gate = fusion_accept_gate(fusion, sources)
    fusion["certification_gate"] = gate
    if not gate["accepted"]:
        fusion["lineage"]["decomposable"] = False
        fusion["refused"] = True
        fusion["refusal_reason"] = gate["reason"]
    return fusion


def _lineage_by_id(fusion: dict) -> dict[str, dict]:
    out = {}
    for src in (fusion.get("lineage") or {}).get("sources") or []:
        if src.get("id"):
            out[str(src["id"])] = src
    return out


def decompose(fusion: dict) -> dict:
    """Recover per-source components. Missing license/credit is a named defect."""
    by_id = _lineage_by_id(fusion)
    grouped: dict[str, list[dict]] = {}
    for st in fusion.get("stages") or []:
        sid = str(st.get("source_id") or "")
        grouped.setdefault(sid, []).append(dict(st))
    components = []
    reports = []
    defects = []
    # Include lineage sources even if they lost every stage (capability/provenance loss).
    source_ids = list(dict.fromkeys(list(by_id.keys()) + list(grouped.keys())))
    for sid in source_ids:
        meta = by_id.get(sid) or {}
        stages = grouped.get(sid) or []
        license_id = str(meta.get("license") or "")
        credit = str(meta.get("credit") or "")
        license_present = bool(license_id.strip())
        credit_present = bool(credit.strip())
        if not license_present or not credit_present:
            defects.append(
                {
                    "source_id": sid,
                    "defect": LOST_PROVENANCE,
                    "license_present": license_present,
                    "credit_present": credit_present,
                }
            )
        caps = set()
        for st in stages:
            caps.update(st.get("capabilities") or [])
        if not caps and meta:
            # lineage claimed a source that left no stages
            caps = set()
        component = {
            "id": sid or "orphan",
            "version": meta.get("version") or "1.0.0",
            "license": license_id,
            "spdx": meta.get("spdx") or license_id,
            "credit": credit,
            "capabilities": sorted(caps),
            "stages": [
                {
                    "id": st.get("id"),
                    "kind": st.get("kind"),
                    "capabilities": list(st.get("capabilities") or []),
                    "source_id": sid,
                }
                for st in stages
            ],
            "recovered_from": fusion.get("id"),
        }
        components.append(component)
        reports.append(
            {
                "source_id": component["id"],
                "license_present": license_present,
                "credit_present": credit_present,
                "license": license_id,
                "credit": credit,
                "stage_count": len(stages),
                "capabilities": sorted(caps),
                "executed": False,
                "terminal_state": "",
            }
        )
    if not source_ids:
        defects.append({"source_id": "", "defect": LOST_PROVENANCE, "reason": "empty-lineage"})
    return {
        "fusion_id": fusion.get("id"),
        "components": components,
        "reports": reports,
        "defects": defects,
        "fingerprint": structural_fingerprint(fusion),
    }


def recompose(components: list[dict], fusion_id: str) -> dict:
    sources = []
    for c in components:
        sources.append(
            {
                "id": c["id"],
                "version": c.get("version") or "1.0.0",
                "license": c.get("license") or "",
                "spdx": c.get("spdx") or c.get("license") or "",
                "credit": c.get("credit") or "",
                "capabilities": list(c.get("capabilities") or []),
                "stages": list(c.get("stages") or []),
            }
        )
    return fuse_union(sources, fusion_id)


def strip_license(fusion: dict, source_id: str) -> dict:
    cloned = copy.deepcopy(fusion)
    for src in (cloned.get("lineage") or {}).get("sources") or []:
        if src.get("id") == source_id:
            src["license"] = ""
            src["spdx"] = ""
    for st in cloned.get("stages") or []:
        if st.get("source_id") == source_id:
            st["source_license"] = ""
    return cloned


def drop_capability(fusion: dict, capability: str) -> dict:
    cloned = copy.deepcopy(fusion)
    cloned["capabilities"] = [c for c in (cloned.get("capabilities") or []) if c != capability]
    cloned["stages"] = [
        st
        for st in (cloned.get("stages") or [])
        if capability not in (st.get("capabilities") or []) and st.get("kind") != capability
    ]
    return cloned


def pad_noop_stages(source: dict, extra: int = 2) -> dict:
    cloned = copy.deepcopy(source)
    for i in range(extra):
        cloned.setdefault("stages", []).append(
            {
                "id": f"noop-{i}",
                "kind": "tokenize",
                "capabilities": list(source.get("capabilities") or [])[:1] or ["tokenize"],
            }
        )
    return cloned


def attach_execution(decomp: dict, cases_by_id: dict[str, dict]) -> dict:
    for comp, report in zip(decomp["components"], decomp["reports"]):
        case = cases_by_id.get(comp["id"]) or {"text": ""}
        result = execute(comp, case)
        report["executed"] = bool(result.get("executed"))
        report["terminal_state"] = str(result.get("state") or "")
        report["terminal"] = bool(result.get("terminal"))
        report["stages_run"] = list(result.get("stages_run") or [])
        report["tokens"] = list(result.get("tokens") or [])
        report["execute_reason"] = str(result.get("reason") or "")
    return decomp
