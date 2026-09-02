#!/usr/bin/env python3
"""Probe 1: helper unit test on a known file + three-route on docs/alpha.md.

Uses the canonical blob_bytes helper. Probe 2 re-measures a different file
with raw git, not this module.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MG = REPO / "tools" / "measure-guard"
sys.path.insert(0, str(MG))
sys.path.insert(0, str(MG / "tests"))

import blobread as B  # noqa: E402
import crlf_export_repo as F  # noqa: E402
import test_blobread as tests  # noqa: E402
import three_route as T  # noqa: E402

OUT = HERE / "probe1-helper-three-route.raw.json"
ART = REPO / "command-center/receipts/IMP-0440.json"
SENTINEL = "SENTINEL:IMP-0440:BLOB-HELPER-SINGLE-SOURCE"


def _fail(msg: str, payload: dict | None = None) -> int:
    if payload:
        OUT.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2, default=str)[:4000])
    print(f"FAILED:IMP-0440-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared:{st}")
    if SENTINEL not in text:
        return _fail("sentinel-absent")

    known = tests.test_known_file_blob_bytes()
    refuses = tests.test_helper_refuses_archive_in_source()
    wt = tests.test_worktree_is_not_oracle()

    with tempfile.TemporaryDirectory(prefix="imp0440-p1-") as td:
        info = F.make_crlf_export_repo(Path(td) / "repo")
        routes = T.three_route(info["root"], F.ALPHA, "HEAD")
        helper = B.blob_bytes("HEAD", F.ALPHA, repo=info["root"])

    payload = {
        "probe": "probe1-helper-three-route",
        "unit_id": "IMP-0440",
        "file": F.ALPHA,
        "known_file": known,
        "helper_refuses_archive": refuses,
        "worktree_not_oracle": wt,
        "three_route": routes,
        "helper_bytes": len(helper),
        "pass": True,
    }
    if not (
        routes["archive_differs_from_blob"]
        and routes["helper_equals_cat_file"]
        and routes["cat_file_equals_show"]
        and routes["identical_after_lf_normalisation"]
        and routes["routes"]["git archive + tar -x"]["crlf"] > 0
        and routes["routes"]["blob_bytes helper"]["crlf"] == 0
        and helper == F.ALPHA_BODY
    ):
        payload["pass"] = False
        return _fail("three-route or helper mismatch", payload)

    OUT.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, default=str))
    print(
        f"file={F.ALPHA} archive_crlf={routes['routes']['git archive + tar -x']['crlf']} "
        f"blob_crlf={routes['routes']['blob_bytes helper']['crlf']} "
        f"identical_after_lf={routes['identical_after_lf_normalisation']}"
    )
    print("SUCCESS:IMP-0440-probe1 helper unit test and three-route on docs/alpha.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
