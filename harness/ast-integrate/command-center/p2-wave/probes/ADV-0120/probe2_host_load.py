#!/usr/bin/env python3
"""Probe 2: host load of unrelated hooks/MCP/settings/skills after uninstall.

Mechanically different from inventory: execute hook/MCP scripts and read
markers. A shared JSON document left syntactically valid but emptied must
fail this probe while probe 1 stays green. Control: same host must load
before uninstall.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import drill as D  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0120-uninstall-collateral-damage.json"
SENTINEL = "SUCCESS:ADV-0120"


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0120-probe2 {msg}")
    return 1


def main() -> int:
    report = D.measure()
    payload = {
        "pre_uninstall_host_ok": report["pre_uninstall_host_ok"],
        "production_host_load_ok": report["production_host_load_ok"],
        "naive_host_load_ok": report["naive_host_load_ok"],
        "naive_inventory_intact": report["naive_inventory_intact"],
        "naive_split_inventory_pass_load_fail": report[
            "naive_split_inventory_pass_load_fail"
        ],
        "production_hooks": report["production"]["post_boot"][
            "unrelated_hooks_loaded"
        ],
        "naive_hooks": report["naive_empty"]["post_boot"][
            "unrelated_hooks_loaded"
        ],
        "pass": (
            report["pre_uninstall_host_ok"]
            and report["production_host_load_ok"]
            and report["naive_split_inventory_pass_load_fail"]
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    if not report["pre_uninstall_host_ok"]:
        return fail("host did not load unrelated components before uninstall")
    if not report["production_host_load_ok"]:
        return fail("host failed to load unrelated components after production uninstall")
    if report["naive_host_load_ok"]:
        return fail("naive emptied JSON still loaded; load probe is inert")
    if not report["naive_inventory_intact"]:
        return fail("naive mutant removed files; split vs inventory is lost")
    if not report["naive_split_inventory_pass_load_fail"]:
        return fail("naive mutant did not demonstrate inventory-pass/load-fail")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    measured = doc.get("measured") or {}
    if measured.get("production_host_load_ok") is not True:
        return fail("artifact host-load flag drifted")
    if measured.get("naive_split_inventory_pass_load_fail") is not True:
        return fail("artifact naive-split flag drifted")

    print(
        "pre_ok=True post_ok=True naive_load="
        f"{report['naive_host_load_ok']} split="
        f"{report['naive_split_inventory_pass_load_fail']}"
    )
    print("SUCCESS:ADV-0120-probe2 host-load after uninstall")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
