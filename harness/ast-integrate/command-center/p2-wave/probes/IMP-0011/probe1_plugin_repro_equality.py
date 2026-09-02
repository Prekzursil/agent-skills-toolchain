#!/usr/bin/env python3
"""Named probe 1: CI job plugin-repro double-build + windows-regime equality.

Live: inspect both workflow copies, run three-way pack, require identical
sha256 across linux-1, linux-2, and windows-regime (CRLF worktree, blob pack).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "plugin"))

from plugin import repro_gate as G  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0011.json"
SENTINEL = "SUCCESS:IMP-0011"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0011-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:IMP-0011-probe1 sentinel-absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0011":
        print("FAILED:IMP-0011-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0011-probe1 self-declared", doc.get("state"))
        return 1

    try:
        wf = G.inspect_workflows(REPO)
    except G.WorkflowStructuralError as exc:
        print(f"FAILED:IMP-0011-probe1 workflow {exc}")
        return 1
    if wf.get("job") != "plugin-repro" or not wf.get("ok"):
        print("FAILED:IMP-0011-probe1 job name")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0011-p1-") as tmp:
        tri = G.three_way(Path(tmp) / "dist")

    sha = tri["compare"]["sha256"]
    if not (
        tri["linux_1"]["sha256"] == sha
        and tri["linux_2"]["sha256"] == sha
        and tri["windows"]["sha256"] == sha
    ):
        print("FAILED:IMP-0011-probe1 digest inequality")
        return 1
    if tri["linux_1"]["invocation_id"] == tri["linux_2"]["invocation_id"]:
        print("FAILED:IMP-0011-probe1 cached first build")
        return 1
    if tri["windows"]["worktree_crlf"] < 1:
        print("FAILED:IMP-0011-probe1 windows worktree has no CRLF")
        return 1
    if tri["windows"]["blob_crlf"] != 0:
        print("FAILED:IMP-0011-probe1 blob CRLF")
        return 1
    if tri["windows"]["byte_source"] != "git-cat-file-blob":
        print("FAILED:IMP-0011-probe1 byte source", tri["windows"]["byte_source"])
        return 1
    if tri["linux_1"]["inject_timestamp"] or tri["linux_2"]["inject_timestamp"]:
        print("FAILED:IMP-0011-probe1 unexpected timestamp")
        return 1

    summary = {
        "probe": "probe1-plugin-repro-equality",
        "unit_id": "IMP-0011",
        "job": "plugin-repro",
        "sha256": sha,
        "linux_1_invocation": tri["linux_1"]["invocation_id"],
        "linux_2_invocation": tri["linux_2"]["invocation_id"],
        "windows_worktree_crlf": tri["windows"]["worktree_crlf"],
        "windows_blob_crlf": tri["windows"]["blob_crlf"],
        "windows_byte_source": tri["windows"]["byte_source"],
        "two_log_sections": True,
        "workflows": [row["rel"] for row in wf["workflows"]],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:IMP-0011-probe1 plugin-repro three-way digest equality")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
