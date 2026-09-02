#!/usr/bin/env python3
"""Probe 1: four packaged journeys, file postconditions, source tree not on sys.path."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = H.REPO / H.OUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 800:
        print("FAILED:CNF-0039-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0039":
        print("FAILED:CNF-0039-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0039-probe1 self-declared {doc.get('state')}")
        return 1
    if H.SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0039-probe1 sentinel absent")
        return 1

    wheel = H.write_wheel()
    install_root = HERE / "_install-probe1"
    if install_root.exists():
        shutil.rmtree(install_root)
    H.install_wheel(wheel, install_root)
    scratch = HERE / "_scratch-probe1"
    if scratch.exists():
        shutil.rmtree(scratch)
    out_dir = scratch / "out"
    cwd = scratch / "cwd"
    out_dir.mkdir(parents=True)
    cwd.mkdir(parents=True)

    rows = H.run_all_journeys(str(install_root.resolve()), out_dir, cwd)
    failed = []
    for row in rows:
        jid = row["spec"]["id"]
        pkg_ok = row["run"]["exit_code"] == 0 and row["probe"]["pass"]
        repo_on = row["repo_on_sys_path"]
        print(
            f"journey={jid} rc={row['run']['exit_code']} "
            f"bytes={row['run']['bytes']} post={row['probe']['pass']} "
            f"repo_on_path={repo_on}"
        )
        print(row["probe"]["output"])
        if row["run"]["exit_code"] != 0:
            print("cli:", row["run"]["output"][-400:])
        if not pkg_ok:
            failed.append(jid)
        if repo_on:
            failed.append(f"{jid}:repo-on-sys-path")
        if row["run"]["bytes"] < row["spec"]["min_bytes"]:
            failed.append(f"{jid}:tiny")

    body = H.report_body(doc)
    journeys = doc.get("journeys") or body.get("journeys") or []
    art_n = len(journeys)
    if art_n != 4:
        print(f"FAILED:CNF-0039-probe1 artifact journeys={art_n} want=4")
        return 1
    if failed:
        print("FAILED:CNF-0039-probe1", failed)
        return 1
    vs = doc.get("source_tree_vs_package") or body.get("source_tree_vs_package") or {}
    if not vs.get("all_packaged_postconditions_pass"):
        print("FAILED:CNF-0039-probe1 artifact does not claim packaged pass")
        return 1
    print("SUCCESS:CNF-0039-probe1 packaged journeys file postconditions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
