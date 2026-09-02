#!/usr/bin/env python3
"""Probe 1: both-directions reporting and sample-adequacy (never a percentage)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from reconcile import MIN_EXECUTIONS, mutant_unexercised_as_overgrant  # noqa: E402
from window import delivering_agent_window, run_adequate, run_thin  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:ARC-0108-probe1 {msg}")
    return 1


def _labels(rows: list[dict]) -> set[str]:
    return {str(r.get("label") or "") for r in rows}


def _has(rows: list[dict], cap: str, perm: str) -> dict | None:
    for r in rows:
        if r.get("capability_id") == cap and r.get("permission") == perm:
            return r
    return None


def main() -> int:
    adequate = run_adequate()
    thin = run_thin()
    agent = delivering_agent_window()

    if adequate["sample_size"] < MIN_EXECUTIONS:
        return _fail(f"adequate sample_size={adequate['sample_size']}")
    if adequate["adequacy"] != "ADEQUATE":
        return _fail(f"adequacy={adequate['adequacy']}")
    if thin["adequacy"] != "INADEQUATE":
        return _fail(f"thin adequacy={thin['adequacy']}")
    if thin["sample_size"] >= MIN_EXECUTIONS:
        return _fail("thin window is not thin")
    if agent["adequacy"] != "NO-RECORDS":
        return _fail("agent window must be NO-RECORDS")

    for name, doc in ("adequate", adequate), ("thin", thin), ("agent", agent):
        if "compliance_percent" in doc or "compliance_percentage" in doc:
            return _fail(f"{name} emitted a compliance percentage")
        if doc.get("verdict_shape") != "two-directions":
            return _fail(f"{name} collapsed to a single verdict shape")
        if "declared_not_observed" not in doc or "observed_not_declared" not in doc:
            return _fail(f"{name} missing a direction list")

    if _labels(thin["declared_not_observed"]) - {"NOT-CHECKED", ""} and thin[
        "declared_not_observed"
    ]:
        if any(r["label"] != "NOT-CHECKED" for r in thin["declared_not_observed"]):
            return _fail("thin declared_not_observed not NOT-CHECKED")
    if any(r["label"] != "NOT-CHECKED" for r in thin["observed_not_declared"]):
        return _fail("thin observed_not_declared not NOT-CHECKED")
    if any(r["label"] != "NOT-CHECKED" for r in thin["exercised_and_declared"]):
        return _fail("thin matched not NOT-CHECKED")

    a = adequate["declared_not_observed"]
    b = adequate["observed_not_declared"]
    if any(r["label"] == "OVER-GRANT" for r in a):
        return _fail("UNEXERCISED reported as OVER-GRANT")
    if not a:
        return _fail("direction A empty; expected UNEXERCISED grants")
    if not b:
        return _fail("direction B empty; expected UNDER-DECLARATION")
    if any(r["label"] != "UNEXERCISED" for r in a):
        return _fail(f"direction A labels={_labels(a)}")
    if any(r["label"] != "UNDER-DECLARATION" for r in b):
        return _fail(f"direction B labels={_labels(b)}")

    bash = _has(a, "cap.wide", "tool:Bash")
    net = _has(a, "cap.wide", "net:example.test")
    if bash is None or net is None:
        return _fail("cap.wide Bash/net missing from UNEXERCISED")
    sneak = _has(b, "cap.sneak", "tool:Write")
    grep = _has(b, "cap.reader", "tool:Grep")
    secret = _has(b, "mcp.demo", "tool:mcp.demo/secret")
    skill_path = _has(b, "skill.scoped", "path:data/ok.txt")
    if sneak is None or grep is None or secret is None or skill_path is None:
        return _fail("under-declaration set incomplete")

    if mutant_unexercised_as_overgrant(True) == "UNEXERCISED":
        return _fail("mutant classifier collapsed onto production")
    if mutant_unexercised_as_overgrant(True) != "OVER-GRANT":
        return _fail("mutant control not OVER-GRANT")

    points = adequate.get("enforcement_points") or []
    if len(points) != 1 or ":invoke" not in points[0]:
        return _fail(f"enforcement_points={points}")
    if adequate["deny_count"] < 1 or adequate["allow_count"] < 1:
        return _fail("need both ALLOW and DENY in the adequate window")

    print(
        json.dumps(
            {
                "adequate_sample_size": adequate["sample_size"],
                "thin_sample_size": thin["sample_size"],
                "agent_sample_size": agent["sample_size"],
                "unexercised": len(a),
                "under_declarations": len(b),
                "deny_count": adequate["deny_count"],
                "allow_count": adequate["allow_count"],
                "thin_adequacy": thin["adequacy"],
                "agent_adequacy": agent["adequacy"],
                "percentage_verdict": False,
            },
            sort_keys=True,
        )
    )
    print(
        "both-directions unexercised="
        f"{len(a)} under_declarations={len(b)} "
        f"thin=NOT-CHECKED agent=NOT-CHECKED"
    )
    print("SUCCESS:ARC-0108-probe1 both-directions and sample-adequacy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
