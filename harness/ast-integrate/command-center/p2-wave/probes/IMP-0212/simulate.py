"""Hermetic workflow simulator. Zero network, zero spawns, refuse unemulatable caps."""
from __future__ import annotations

from typing import Any

from ir import EMULATABLE_CAPABILITIES
from validate import topo_stages

# Deliberately unused at runtime. Named so probes can assert the module does not
# import socket/subprocess for execution. Do not add those imports.


def simulate(wf: dict[str, Any], *, initial: dict[str, Any] | None = None) -> dict[str, Any]:
    """Interpret a workflow in-process.

    Unknown or unemulatable capabilities are refused by name. A silently faked
    capability would be worse than a refusal (IMP-0199 acceptance, local adapter).
    """
    receipt: dict[str, Any] = {
        "ok": False,
        "pass": False,
        "error_code": None,
        "refused_capability": None,
        "stage_id": None,
        "stages": [],
        "zero_egress": True,
        "zero_spawn": True,
        "emulator": "IMP-0212-hermetic-local",
        "note": (
            "Local simulation gate for IMP-0212. IMP-0199 (agentspec fake_rail) is "
            "not delivered on this worktree; this emulator does not claim that unit."
        ),
    }
    if not isinstance(wf, dict):
        receipt["error_code"] = "NOT_A_WORKFLOW"
        return receipt

    for st in wf.get("stages") or []:
        if not isinstance(st, dict):
            continue
        cap = st.get("capability")
        if not isinstance(cap, str) or cap not in EMULATABLE_CAPABILITIES:
            receipt["error_code"] = "UNEMULATABLE_CAPABILITY"
            receipt["refused_capability"] = cap
            receipt["stage_id"] = st.get("id")
            receipt["message"] = (
                f"refusing to silently fake capability {cap!r} on stage {st.get('id')!r}"
            )
            return receipt

    ordered, topo_errs = topo_stages(wf)
    if ordered is None:
        receipt["error_code"] = "STATIC_UNSATISFIED"
        receipt["errors"] = topo_errs
        return receipt

    store: dict[str, Any] = dict(initial or {})
    for name in wf.get("initial_inputs") or []:
        store.setdefault(name, {"emulated": True, "name": name})

    results: list[dict[str, Any]] = []
    for st in ordered:
        missing = [inp for inp in st.get("inputs") or [] if inp not in store]
        if missing:
            receipt["error_code"] = "MISSING_INPUT"
            receipt["stage_id"] = st.get("id")
            receipt["message"] = f"missing inputs {missing}"
            receipt["stages"] = results
            return receipt
        for out in st.get("outputs") or []:
            store[out] = {
                "emulated": True,
                "from": st.get("id"),
                "kind": st.get("kind"),
            }
        results.append(
            {
                "id": st.get("id"),
                "kind": st.get("kind"),
                "status": "EMULATED",
                "tool": st.get("tool"),
            }
        )

    receipt["ok"] = True
    receipt["pass"] = True
    receipt["error_code"] = None
    receipt["stages"] = results
    receipt["produced"] = sorted(store)
    return receipt
