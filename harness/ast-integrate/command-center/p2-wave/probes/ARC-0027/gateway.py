#!/usr/bin/env python3
"""Scratch A4 lazy-activation gateway for ARC-0027 permission TOCTOU.

INDEX lists capabilities and does not materialize bodies.
SELECT records a chosen id.
ACTIVATE materializes. The authoritative permission check lives in
authorize_activation when check_epoch == 'activation'. Epochs 'index'
and 'selection' cache ALLOW/DENY and are the failing controls that let
an edited declared grant slip through at use time.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Epoch = Literal["index", "selection", "activation"]
AUTHORITATIVE_CHECK_EPOCH = "activation"
ESCALATED_GRANT = "tool:Bash"
BASE_GRANT = "tool:Read"

ACTIVATION_ENTRY_POINTS = (
    "activate_skill",
    "activate_mcp",
    "activate_workflow",
    "activate_hook",
    "activate_council",
    "select_then_activate",
    "reactivate",
)
NON_ACTIVATION_CONTROLS = ("index_capabilities", "select_capability")


@dataclass
class Ticket:
    outcome: str
    declared: list[str]
    effective_grant: list[str]
    check_epoch: str
    used_cache: bool
    reason: str


@dataclass
class Gateway:
    estate: Path
    check_epoch: Epoch = AUTHORITATIVE_CHECK_EPOCH
    allow: list[str] = field(default_factory=lambda: [BASE_GRANT])
    cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    selected: str | None = None
    materialized: dict[str, dict[str, Any]] = field(default_factory=dict)

    def cap_path(self, cap_id: str) -> Path:
        return self.estate / "capabilities" / f"{cap_id}.json"

    def read_declared(self, cap_id: str) -> list[str]:
        raw = json.loads(self.cap_path(cap_id).read_text(encoding="utf-8"))
        perms = raw.get("permissions") or []
        return [str(p) for p in perms]

    def evaluate_now(self, declared: list[str]) -> str:
        return "ALLOW" if set(declared) <= set(self.allow) else "DENY"

    def record_decision(self, cap_id: str, epoch: str) -> Ticket:
        declared = self.read_declared(cap_id)
        outcome = self.evaluate_now(declared)
        self.cache[cap_id] = {
            "outcome": outcome,
            "declared_at_check": list(declared),
            "epoch": epoch,
        }
        grant = list(declared) if outcome == "ALLOW" else []
        return Ticket(outcome, declared, grant, epoch, False, "fresh-eval")


def load_session(estate: Path) -> list[str]:
    session = estate / "session.json"
    if not session.is_file():
        return [BASE_GRANT]
    data = json.loads(session.read_text(encoding="utf-8"))
    allow = data.get("allow") or [BASE_GRANT]
    return [str(x) for x in allow]


def make_gateway(estate: Path, check_epoch: Epoch) -> Gateway:
    return Gateway(estate=estate, check_epoch=check_epoch, allow=load_session(estate))


def authorize_activation(gw: Gateway, cap_id: str) -> Ticket:
    """Authoritative choke. Every activation entry point must call this."""
    declared = gw.read_declared(cap_id)
    if gw.check_epoch in ("index", "selection"):
        cached = gw.cache.get(cap_id)
        if cached is None:
            return Ticket("DENY", declared, [], gw.check_epoch, True, "no-cached-decision")
        outcome = str(cached["outcome"])
        # Fail-open TOCTOU: cached ALLOW is reused; live declared grant is applied.
        grant = list(declared) if outcome == "ALLOW" else []
        return Ticket(outcome, declared, grant, gw.check_epoch, True, "cached-decision")
    outcome = gw.evaluate_now(declared)
    grant = list(declared) if outcome == "ALLOW" else []
    return Ticket(outcome, declared, grant, AUTHORITATIVE_CHECK_EPOCH, False, "activation-reread")


def _materialize(gw: Gateway, cap_id: str, ticket: Ticket, via: str) -> dict[str, Any]:
    rec = {
        "id": cap_id,
        "via": via,
        "outcome": ticket.outcome,
        "declared": list(ticket.declared),
        "effective_grant": list(ticket.effective_grant),
        "check_epoch": ticket.check_epoch,
        "used_cache": ticket.used_cache,
        "reason": ticket.reason,
        "permission_ticket": (
            f"a4-activate:{cap_id}:{ticket.outcome}"
            if ticket.outcome == "ALLOW"
            else None
        ),
    }
    if ticket.outcome == "ALLOW":
        gw.materialized[cap_id] = rec
    return rec


def index_capabilities(gw: Gateway) -> dict[str, Any]:
    caps_dir = gw.estate / "capabilities"
    ids = sorted(p.stem for p in caps_dir.glob("*.json"))
    indexed = []
    for cap_id in ids:
        row: dict[str, Any] = {
            "id": cap_id,
            "declared": gw.read_declared(cap_id),
            "materialized": False,
        }
        if gw.check_epoch == "index":
            ticket = gw.record_decision(cap_id, "index")
            row["check"] = ticket.outcome
            row["effective_grant"] = ticket.effective_grant
        indexed.append(row)
    return {"ids": ids, "rows": indexed, "epoch": gw.check_epoch}


def select_capability(gw: Gateway, cap_id: str) -> dict[str, Any]:
    gw.selected = cap_id
    row: dict[str, Any] = {"id": cap_id, "selected": True}
    if gw.check_epoch == "selection":
        ticket = gw.record_decision(cap_id, "selection")
        row["check"] = ticket.outcome
        row["effective_grant"] = ticket.effective_grant
    return row


def activate_skill(gw: Gateway, cap_id: str) -> dict[str, Any]:
    return _materialize(gw, cap_id, authorize_activation(gw, cap_id), "activate_skill")


def activate_mcp(gw: Gateway, cap_id: str) -> dict[str, Any]:
    return _materialize(gw, cap_id, authorize_activation(gw, cap_id), "activate_mcp")


def activate_workflow(gw: Gateway, cap_id: str) -> dict[str, Any]:
    return _materialize(gw, cap_id, authorize_activation(gw, cap_id), "activate_workflow")


def activate_hook(gw: Gateway, cap_id: str) -> dict[str, Any]:
    return _materialize(gw, cap_id, authorize_activation(gw, cap_id), "activate_hook")


def activate_council(gw: Gateway, cap_id: str) -> dict[str, Any]:
    return _materialize(gw, cap_id, authorize_activation(gw, cap_id), "activate_council")


def select_then_activate(gw: Gateway, cap_id: str) -> dict[str, Any]:
    select_capability(gw, cap_id)
    return _materialize(
        gw, cap_id, authorize_activation(gw, cap_id), "select_then_activate"
    )


def reactivate(gw: Gateway, cap_id: str) -> dict[str, Any]:
    gw.materialized.pop(cap_id, None)
    return _materialize(gw, cap_id, authorize_activation(gw, cap_id), "reactivate")


ENTRY_DISPATCH = {
    "activate_skill": activate_skill,
    "activate_mcp": activate_mcp,
    "activate_workflow": activate_workflow,
    "activate_hook": activate_hook,
    "activate_council": activate_council,
    "select_then_activate": select_then_activate,
    "reactivate": reactivate,
}


def edit_declared(estate: Path, cap_id: str, permissions: list[str]) -> list[str]:
    path = estate / "capabilities" / f"{cap_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["permissions"] = list(permissions)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return list(permissions)
