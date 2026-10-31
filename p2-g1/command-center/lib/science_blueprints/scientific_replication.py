"""Scientific replication protocol gate."""
from __future__ import annotations


def replicate(spec: dict) -> dict:
    steps = spec.get("steps") or []
    required = {"declare-d", "collect", "report-effect-size"}
    ok = bool(spec.get("effect_size")) and bool(spec.get("protocol_id")) and required.issubset(set(steps))
    return {"ok": ok, "protocol_id": spec.get("protocol_id"), "missing": sorted(required - set(steps))}
