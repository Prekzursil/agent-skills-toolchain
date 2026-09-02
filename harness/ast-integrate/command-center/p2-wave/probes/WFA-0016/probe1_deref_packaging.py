#!/usr/bin/env python3
"""Probe 1: caret-free tag deref + packaging mismatch vs match (evidence B)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0016-sweep-releases.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0016-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0016" not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    hunt = S.hunt_host_registry()
    live = S.sweep_fixture_world(hunt["join_registry"])
    caret = live["caret_control"]
    if caret.get("caret_deref_refused") is not True:
        return fail("caret form was not refused")
    if caret.get("mangle_differs") is not True:
        return fail("PowerShell mangle did not change caret peel")
    if "^" in "".join(str(x) for x in (caret.get("command") or [])):
        return fail("deref command still contains caret")

    git_dir = HERE / "fixtures/git-world/pack-match"
    sha = E.deref_tag(git_dir, "v1.0.0")
    if sha != caret.get("rev_list_sha"):
        return fail("live deref drifted from control")
    rec_caret = ((doc.get("fixture_sweep") or {}).get("caret_control") or {})
    rec_sha = str(rec_caret.get("rev_list_sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", rec_sha):
        return fail("artifact deref sha missing")
    if rec_sha != sha:
        return fail("artifact deref sha != live")
    if rec_caret.get("caret_form_used") is True:
        return fail("artifact claims caret form was used")
    if rec_caret.get("caret_deref_refused") is not True:
        return fail("artifact missing caret refusal")

    packaging = live["packaging_findings"]
    if not packaging:
        return fail("packaging mismatch not detected")
    if not any(p.get("repo") == "owner/pack-mismatch" for p in packaging):
        return fail("mismatch repo not named")
    rec_pack = (doc.get("fixture_sweep") or {}).get("packaging_findings") or []
    if not rec_pack:
        return fail("artifact missing packaging findings")

    match_repo = next(r for r in live["repos"] if r["name"] == "owner/pack-match")
    asset = match_repo["releases"][0]["assets"][0]
    if (asset.get("tag_compare") or {}).get("verdict") != "MATCH":
        return fail("pack-match was not MATCH")
    if asset.get("classification") == "EMPTY":
        return fail("pack-match classified EMPTY")

    out = {
        "probe": "probe1-deref-packaging",
        "unit_id": "WFA-0016",
        "caret_refused": True,
        "powershell_mangle_differs": True,
        "deref_sha": sha,
        "packaging_findings": len(packaging),
        "match_verdict": "MATCH",
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"caret_refused={caret['caret_deref_refused']} "
        f"mangle={caret['powershell_mangled']} "
        f"packaging={len(packaging)} match=MATCH"
    )
    print("SUCCESS:WFA-0016-probe1 caret-free deref and packaging compare")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
