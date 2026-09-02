#!/usr/bin/env python3
"""Probe 1: detector control — canary planted INSIDE an artifact; both scanners fire.

Also proves planting in env and local config, and that the leaky producer is
the dirty both-states pair. Does not import entropy_scan (mechanical split).
Does not print the canary body.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import pattern_scan as P  # noqa: E402
import scenario as S  # noqa: E402
from canary import PREFIX  # noqa: E402

ART = REPO / "command-center/receipts/TST-0206.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0206-probe1 {msg}")
    return 1


def main() -> int:
    src = (HERE / "pattern_scan.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(n.name.split(".", 1)[0] == "entropy_scan" for n in node.names):
                return fail("pattern_scan.py imports entropy_scan")
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.split(".", 1)[0] == "entropy_scan":
                return fail("pattern_scan.py imports entropy_scan")

    run = S.run_scenario()
    pub = run.public
    plant = pub["planting"]
    ctl = pub["detector_control"]
    agr = pub["agreement"]
    print(
        json.dumps(
            {
                "probe": "probe1-detector-control",
                "unit_id": "TST-0206",
                "canary_prefix": PREFIX,
                "canary_sha256": pub["canary_sha256"],
                "env_contains_canary": plant["env_contains_canary"],
                "config_contains_canary": plant["config_contains_canary"],
                "scanners_see_config": plant["scanners_see_config"],
                "control_pattern_canary_hits": ctl["pattern_canary_hits"],
                "control_entropy_canary_hits": ctl["entropy_canary_hits"],
                "control_agree": ctl.get("agree"),
                "leaky_agree": agr["produced_leaky_present"],
            },
            sort_keys=True,
        )
    )
    if not plant["env_contains_canary"]:
        return fail("canary was not planted in env")
    if not plant["config_contains_canary"]:
        return fail("canary was not planted in local config")
    if not plant["scanners_see_config"]:
        return fail("scanners silent on planted local config")
    if ctl["pattern_canary_hits"] < 1:
        return fail("pattern scanner silent on planted-inside-artifact control")
    if ctl["entropy_canary_hits"] < 1:
        return fail("entropy scanner silent on planted-inside-artifact control")
    if not ctl.get("agree"):
        return fail("scanners disagreed on detector control")
    if not agr["produced_leaky_present"]:
        return fail("leaky-producer dirty state did not fire both scanners")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if "SUCCESS:TST-0206" not in text:
        return fail("sentinel-absent")
    if run.contains_canary(text):
        return fail("receipt contains this run's canary body")
    leaked = P.canary_hits(
        P.scan_path(ART, rel="command-center/receipts/TST-0206.json")
    )
    if leaked:
        return fail("receipt matches canary prefix-plus-suffix pattern")
    ev = doc.get("evidence") or []
    if not isinstance(ev, list) or len(ev) < 2:
        return fail("evidence[] missing two independent signals")
    ids = {item.get("id") for item in ev if isinstance(item, dict)}
    if "pattern-scanner" not in ids or "entropy-scanner" not in ids:
        return fail("receipt evidence missing pattern-scanner and entropy-scanner")
    print("SUCCESS:TST-0206-probe1 detector control both scanners fire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
