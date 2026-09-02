"""Attempted load of a blueprint document into a local WorkflowIR contract.

WFA-0044's vendor-neutral spec is absent on this tree. This loader is NOT a
second execution runtime: it only binds stages, gates, stop, dag/topo, roles
and a source_anchor per node. A missing required field is a load-error.
"""
from __future__ import annotations

from typing import Any

NATIVE_STATES = frozenset(
    {"NATIVE", "EXECUTABLE", "SHIPPED", "READY", "ADOPT", "PRODUCTION"}
)
NATIVE_TIERS = frozenset({"native", "executable", "flagship", "smoke", "e2e"})
FLAGSHIP_TIERS = frozenset({"flagship", "e2e", "end-to-end"})


def declared_discovery_only(doc: dict[str, Any]) -> bool:
    for key in ("discovery_only", "placeholder", "is_placeholder"):
        if doc.get(key) is True:
            return True
    status = str(doc.get("status") or "").lower()
    if "placeholder" in status or status.startswith("discovery"):
        return True
    return False


def declared_state(doc: dict[str, Any]) -> str:
    return str(doc.get("state") or doc.get("status") or "").strip()


def declared_quality_tier(doc: dict[str, Any]) -> str:
    raw = doc.get("quality_tier") or doc.get("tier") or doc.get("quality") or ""
    return str(raw).strip().lower()


def declares_native(doc: dict[str, Any]) -> bool:
    if declared_discovery_only(doc):
        return False
    st = declared_state(doc).upper()
    if st in NATIVE_STATES:
        return True
    tier = declared_quality_tier(doc)
    return tier in NATIVE_TIERS and tier != ""


def declares_flagship(doc: dict[str, Any]) -> bool:
    tier = declared_quality_tier(doc)
    if tier in FLAGSHIP_TIERS:
        return True
    flag = doc.get("flagship")
    return flag is True


def _anchor(rel: str, bid: str, node_id: str) -> str:
    return f"{rel}#{bid}/{node_id}"


def load_ir(doc: Any, *, rel: str, bid: str) -> dict[str, Any]:
    """Return {ok, ir, error, source_anchor_injected}."""
    if not isinstance(doc, dict):
        return {
            "ok": False,
            "ir": None,
            "error": "load-error:document-not-object",
            "source_anchor_injected": False,
        }
    ident = str(doc.get("id") or bid or "").strip()
    if not ident:
        return {
            "ok": False,
            "ir": None,
            "error": "load-error:missing-id",
            "source_anchor_injected": False,
        }
    stages = doc.get("stages")
    if not isinstance(stages, list) or not stages:
        return {
            "ok": False,
            "ir": None,
            "error": "load-error:missing-or-empty-stages",
            "source_anchor_injected": False,
        }
    ir_stages: list[dict[str, Any]] = []
    injected = False
    for i, stage in enumerate(stages):
        if not isinstance(stage, dict):
            return {
                "ok": False,
                "ir": None,
                "error": f"load-error:stage-not-object:{i}",
                "source_anchor_injected": injected,
            }
        sid = str(stage.get("id") or stage.get("name") or f"stage-{i}").strip()
        kind = str(stage.get("kind") or "").strip()
        if not kind:
            return {
                "ok": False,
                "ir": None,
                "error": f"load-error:stage-missing-kind:{sid}",
                "source_anchor_injected": injected,
            }
        anchor = stage.get("source_anchor")
        if not isinstance(anchor, str) or not anchor.strip():
            anchor = _anchor(rel, ident, sid)
            injected = True
        ir_stages.append(
            {
                "id": sid,
                "kind": kind,
                "inputs": list(stage.get("inputs") or []),
                "outputs": list(stage.get("outputs") or []),
                "gate": stage.get("gate"),
                "fan_out": stage.get("fan_out"),
                "script": stage.get("script"),
                "source_anchor": anchor,
            }
        )
    stop = doc.get("stop") if isinstance(doc.get("stop"), dict) else None
    if stop is None and isinstance(doc.get("stopping"), dict):
        stop = dict(doc.get("stopping") or {})
    gates = doc.get("gates")
    if not isinstance(gates, list):
        gates = []
    dag = doc.get("dag") if isinstance(doc.get("dag"), list) else []
    topo = doc.get("topo") if isinstance(doc.get("topo"), list) else []
    roles = doc.get("roles") if isinstance(doc.get("roles"), list) else []
    root_anchor = doc.get("source_anchor")
    if not isinstance(root_anchor, str) or not root_anchor.strip():
        root_anchor = _anchor(rel, ident, "root")
        injected = True
    ir = {
        "id": ident,
        "source_anchor": root_anchor,
        "stages": ir_stages,
        "gates": gates,
        "stop": stop or {"on_error": "unspecified"},
        "dag": dag,
        "topo": topo,
        "roles": roles,
        "lineage": doc.get("lineage") if isinstance(doc.get("lineage"), dict) else {},
        "execution_semantics": None,
    }
    return {
        "ok": True,
        "ir": ir,
        "error": None,
        "source_anchor_injected": injected,
    }
