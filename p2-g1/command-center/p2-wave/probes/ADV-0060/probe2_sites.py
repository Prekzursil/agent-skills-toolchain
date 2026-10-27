#!/usr/bin/env python3
"""Named probe 2: AST invocation-site enum joined to a live subprocess trace."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lifecycle as L  # noqa: E402

ART = L.REPO / L.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0060-probe2 {msg}")
    return 1


def main() -> int:
    m = L.measure()
    report = L.probe2_report(m)
    print(report, end="")
    if m["install_exec_site_count"] < 1:
        return fail("installer has no subprocess/exec site; enum is inert")
    if m["implicit_subprocess_calls"] != 0:
        return fail("implicit install spawned a subprocess")
    if m["naive_subprocess_calls"] < 1:
        return fail("naive control did not spawn subprocess.run")
    if m["gated_subprocess_calls"] < 1:
        return fail("owner-gated arm did not spawn subprocess.run")
    if m["build_subprocess_calls"] != 0:
        return fail("scripts.build was invoked; enum/join mismatch vs installer")
    if m["uninstall_api_present"] is False and m["verdicts"]["T5-uninstall-hook"] != "NOT-CHECKED":
        return fail("absent uninstall pipeline must be NOT-CHECKED, not safe")
    if m["verdicts"]["T9-host-automatic-hook-enforcement"] != "NOT-CHECKED":
        return fail("absent host hook runner must be NOT-CHECKED, not safe")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return fail("artifact-unparseable")
    if not isinstance(doc, dict):
        return fail("artifact-not-object")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if L.catalog_sentinel() not in text:
        return fail("sentinel-absent")
    if L.PROBE2_NAME not in text:
        return fail("probe2-name-absent")
    raw = ""
    for p in doc.get("named_probes") or []:
        if isinstance(p, dict) and p.get("id") == "probe2":
            raw = str(p.get("raw_output") or "")
    if raw != report:
        return fail("named-probe2-raw-mismatch")
    live_ids = {t["id"]: t["verdict"] for t in L.targets_from(m)}
    art_ids = {}
    for t in doc.get("targets") or []:
        if not isinstance(t, dict):
            continue
        tid = t.get("id") or t.get("target_id")
        art_ids[tid] = t.get("verdict")
    if live_ids != art_ids:
        return fail("target-verdict-drift")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        return fail("reviewer-not-independent")
    if str(reviewer.get("reviewer_id") or "") != "ADV-0060-probe2-invocation-site-join":
        return fail("reviewer-id")
    print("SUCCESS:ADV-0060-probe2 invocation-site-join")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
