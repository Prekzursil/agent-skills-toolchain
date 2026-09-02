#!/usr/bin/env python3
"""Deterministic auto-composer: task description + risk tier -> dials + explanation."""
from __future__ import annotations

from typing import Any

from rules import (
    CLASS_OVERLAY,
    DEFAULTS,
    DIALS,
    RISK_BASE,
    TASK_CLASS_RULES,
    rule_table,
)

TIERS = frozenset({"T0", "T1", "T2", "T3", "T4"})


def classify(task_description: str, rules: list[dict] | None = None) -> tuple[str, str]:
    text = (task_description or "").lower()
    for rule in rules if rules is not None else TASK_CLASS_RULES:
        if rule.get("fallback"):
            return str(rule["class"]), str(rule["id"])
        for kw in rule.get("any_keywords") or []:
            if kw.lower() in text:
                return str(rule["class"]), str(rule["id"])
    return "general", "TC-general"


def _copy_dials(src: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in DIALS:
        val = src[name]
        out[name] = list(val) if isinstance(val, list) else val
    return out


def apply_tables(
    risk_tier: str, task_class: str, table: dict | None = None
) -> tuple[dict[str, Any], list[dict]]:
    """Apply published tables. table=None uses live rules.py objects."""
    trace: list[dict] = []
    if table is None:
        if risk_tier not in RISK_BASE:
            raise ValueError(f"unknown risk_tier {risk_tier!r}")
        base = RISK_BASE[risk_tier]
        chosen = _copy_dials(base["dials"])
        last_setter = {name: base["id"] for name in DIALS}
        last_prose = {name: base["prose"] for name in DIALS}
        trace.append({"rule_id": base["id"], "prose": base["prose"], "dials": dict(chosen)})
        overlay = CLASS_OVERLAY.get((risk_tier, task_class))
        if overlay:
            for name, val in (overlay.get("dials") or {}).items():
                chosen[name] = list(val) if isinstance(val, list) else val
                last_setter[name] = overlay["id"]
                last_prose[name] = overlay["prose"]
            for role in overlay.get("roles_add") or []:
                if role not in chosen["roles"]:
                    chosen["roles"] = list(chosen["roles"]) + [role]
                    last_setter["roles"] = overlay["id"]
                    last_prose["roles"] = overlay["prose"]
            trace.append(
                {
                    "rule_id": overlay["id"],
                    "prose": overlay["prose"],
                    "dials": overlay.get("dials") or {},
                    "roles_add": list(overlay.get("roles_add") or []),
                }
            )
        return chosen, {
            "trace": trace,
            "last_setter": last_setter,
            "last_prose": last_prose,
        }

    defaults = table["defaults"]
    risk_base = table["risk_base"]
    if risk_tier not in risk_base:
        raise ValueError(f"unknown risk_tier {risk_tier!r}")
    base = risk_base[risk_tier]
    chosen = _copy_dials(base["dials"])
    last_setter = {name: base["id"] for name in defaults}
    last_prose = {name: base["prose"] for name in defaults}
    trace.append({"rule_id": base["id"], "prose": base["prose"], "dials": dict(chosen)})
    overlay = None
    for row in table.get("class_overlays") or []:
        if row.get("risk_tier") == risk_tier and row.get("task_class") == task_class:
            overlay = row
            break
    if overlay:
        for name, val in (overlay.get("dials") or {}).items():
            chosen[name] = list(val) if isinstance(val, list) else val
            last_setter[name] = overlay["id"]
            last_prose[name] = overlay["prose"]
        for role in overlay.get("roles_add") or []:
            if role not in chosen["roles"]:
                chosen["roles"] = list(chosen["roles"]) + [role]
                last_setter["roles"] = overlay["id"]
                last_prose["roles"] = overlay["prose"]
        trace.append(
            {
                "rule_id": overlay["id"],
                "prose": overlay["prose"],
                "dials": overlay.get("dials") or {},
                "roles_add": list(overlay.get("roles_add") or []),
            }
        )
    return chosen, {
        "trace": trace,
        "last_setter": last_setter,
        "last_prose": last_prose,
    }


def _dial_record(
    name: str,
    value: Any,
    default: Any,
    setter: str,
    prose: str,
) -> dict:
    differs = value != default
    if differs:
        reason = (
            f"rule {setter} set {name}={value!s} (default={default!s}): {prose}"
        )
    else:
        reason = f"{name} equals default {default!s}; owner may still override this dial"
    return {
        "dial": name,
        "value": value,
        "default": default,
        "differs_from_default": differs,
        "rule_id": setter,
        "reason": reason,
        "contest": {
            "override_key": name,
            "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
        },
    }


def compose_explanation(
    task_description: str,
    risk_tier: str,
    *,
    table: dict | None = None,
) -> dict:
    if risk_tier not in TIERS:
        raise ValueError(f"risk_tier must be one of {sorted(TIERS)}")
    tbl = table if table is not None else rule_table()
    task_class, class_rule_id = classify(
        task_description, tbl.get("task_class_rules") if table is not None else None
    )
    chosen, meta = apply_tables(risk_tier, task_class, table=table)
    defaults = tbl["defaults"]
    dials = [
        _dial_record(
            name,
            chosen[name],
            defaults[name],
            meta["last_setter"][name],
            meta["last_prose"][name],
        )
        for name in DIALS
    ]
    return {
        "selector_version": "CNL-0013.v1",
        "inputs": {
            "task_description": task_description,
            "risk_tier": risk_tier,
        },
        "task_class": task_class,
        "task_class_rule_id": class_rule_id,
        "dials": dials,
        "trace": meta["trace"],
        "rule_table": tbl,
        "roster": chosen["roles"],
        "protocol": chosen["protocol"],
        "voting_method": chosen["voting_method"],
        "stopping_rule": chosen["stopping_rule"],
    }


def select(task_description: str, risk_tier: str) -> dict:
    return compose_explanation(task_description, risk_tier)


if __name__ == "__main__":
    import json
    import sys

    from rules import FIXTURES

    rows = [select(f["task_description"], f["risk_tier"]) for f in FIXTURES]
    json.dump({"count": len(rows), "rows": rows}, sys.stdout, indent=1)
    sys.stdout.write("\n")
