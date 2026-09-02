#!/usr/bin/env python3
"""Named probe 2: independent bundle-member enumeration."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

ART = L.REPO / L.OUT_REL
LEGAL = L.LEGAL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0024-probe2 {msg}")
    return 1


def main() -> int:
    m = L.measure()
    report = L.format_probe2(m)
    print(report, end="" if report.endswith("\n") else "\n")
    if not m["clean_ok"]:
        return fail("clean-control fixtures did not package")
    if not m["mutant_packages_clean"] or not m["mutant_refuses_token"]:
        return fail("mutant both-states control did not calibrate")
    by_fix = {r["fixture"]: r for r in m["member_rows"]}
    a1 = by_fix.get("A1_token_file_at_repo_root") or {}
    a3 = by_fix.get("A3_dot_git_dir_at_repo_root") or {}
    a4 = by_fix.get("A4_two_gb_blob_at_repo_root") or {}
    if not a1.get("has_env") and not a1.get("token_prefix_in_members"):
        return fail("A1 members do not show a credential/token include")
    if not a3.get("has_dot_git"):
        return fail("A3 members do not include .git")
    if not a4.get("has_2gib"):
        return fail("A4 members do not include a 2 GiB blob")
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
    errs = L.schema_errors(doc)
    if errs:
        return fail(f"schema:{errs[0]}")
    raw = ""
    for p in doc.get("named_probes") or []:
        if isinstance(p, dict) and p.get("id") == "probe2":
            raw = str(p.get("raw_output") or "")
    if raw != report:
        return fail("named-probe2-raw-mismatch")
    live = {t["target_id"]: t["verdict"] for t in m["targets"]}
    for t in doc.get("targets") or []:
        if not isinstance(t, dict):
            continue
        tid = t.get("target_id")
        if t.get("verdict") not in LEGAL:
            return fail(f"illegal-verdict:{tid}")
        if live.get(tid) != t.get("verdict"):
            return fail(f"verdict-drift:{tid}")
    if live.get("dot-git-directory") != "CONFIRMED":
        return fail("dot-git-target-not-confirmed")
    if live.get("unrelated-2gb-tree") != "CONFIRMED":
        return fail("2gb-target-not-confirmed")
    art_overall = doc.get("overall_verdict")
    if art_overall != m["overall_verdict"]:
        return fail("overall-verdict-drift")
    print("SUCCESS:ADV-0024-probe2 bundle-member-enumeration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
