#!/usr/bin/env python3
"""Named probe 1: live validator verdicts for every fixture.

Re-submits the hostile set and the benign control. Requires a named firing
rule on every hostile, a pass on the control, and agreement with the
confirmation artifact's recorded dispositions.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
from validator import EXIT_PASS, load_registry, validate_package  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0113-malicious-plugin-fixtures.json"
SENTINEL = (
    "SUCCESS:CNF-0113 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and every hostile fixture has a "
    "verdict with the firing rule named and the benign control passed. Any other "
    "terminal state is FAILED:CNF-0113 <classification> with the diagnostic tail "
    "attached."
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0113-probe1 confirmation artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNF-0113-probe1 catalog sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0113":
        print("FAILED:CNF-0113-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0113-probe1 self-declared", doc.get("state"))
        return 1

    recorded = {
        r["id"]: r
        for r in (S.domain_get(doc, "fixtures") or [])
        if isinstance(r, dict) and r.get("id")
    }
    registry = load_registry()
    live: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="cnf0113-p1-") as tmp:
        root = Path(tmp)
        for fx in S.FIXTURES:
            result = validate_package(
                S.package_dir(fx),
                registry=registry,
                sandbox=root / str(fx["id"]),
                materialize_files=True,
            )
            live[str(fx["id"])] = result
            rec = recorded.get(str(fx["id"]))
            if rec is None:
                print(f"FAILED:CNF-0113-probe1 artifact missing fixture {fx['id']}")
                return 1
            if result["disposition"] != rec.get("disposition"):
                print(
                    f"FAILED:CNF-0113-probe1 DISCREPANCY {fx['id']} "
                    f"live={result['disposition']} recorded={rec.get('disposition')}"
                )
                return 1
            if result["firing_rule"] != rec.get("firing_rule"):
                print(
                    f"FAILED:CNF-0113-probe1 DISCREPANCY {fx['id']} "
                    f"rule live={result['firing_rule']} recorded={rec.get('firing_rule')}"
                )
                return 1
            if result["exit_code"] != rec.get("exit_code"):
                print(
                    f"FAILED:CNF-0113-probe1 DISCREPANCY {fx['id']} "
                    f"exit live={result['exit_code']} recorded={rec.get('exit_code')}"
                )
                return 1
            if fx["kind"] == "hostile":
                if not result["firing_rule"]:
                    print(f"FAILED:CNF-0113-probe1 {fx['id']} hostile without firing_rule")
                    return 1
                if result["disposition"] not in {"reject", "warn"}:
                    print(
                        f"FAILED:CNF-0113-probe1 {fx['id']} hostile disposition "
                        f"{result['disposition']}"
                    )
                    return 1
            if result["wrote_outside_sandbox"] or result["scripts_executed"]:
                print(f"FAILED:CNF-0113-probe1 {fx['id']} sandbox/script contract broken")
                return 1

    control = live.get("benign-control")
    if not control or control["disposition"] != "pass" or control["exit_code"] != EXIT_PASS:
        print("FAILED:CNF-0113-probe1 benign control did not pass")
        return 1

    hostiles = [fx["id"] for fx in S.FIXTURES if fx["kind"] == "hostile"]
    if len(hostiles) != 5:
        print(f"FAILED:CNF-0113-probe1 hostile count {len(hostiles)}")
        return 1

    print(
        json.dumps(
            {
                "live_dispositions": {k: v["disposition"] for k, v in live.items()},
                "live_rules": {k: v["firing_rule"] for k, v in live.items()},
                "live_exit_codes": {k: v["exit_code"] for k, v in live.items()},
                "benign_passed": True,
                "hostile_named": True,
                "artifact_agrees": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0113-probe1 hostile verdicts and benign control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
