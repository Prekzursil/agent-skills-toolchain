#!/usr/bin/env python3
"""Named probe 1 (IMP-0081): verified mapping, two independent signals.

Signal 1: map_identity reports VERIFIED for a planted git repo whose recorded
provenance matches HEAD.
Signal 2: an independent `git rev-parse HEAD` (not the mapper's resolved_commit
field as the sole check) equals that same recorded SHA.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.federated_identity import (  # noqa: E402
    GitLsRemoteResolver,
    STATUS_VERIFIED,
    init_local_git_repo,
    map_identity,
)

ART = REPO / "command-center" / "receipts" / "IMP-0081.json"


def _require_receipt() -> dict:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0081-probe1 receipt missing")
        raise SystemExit(1)
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0081-probe1 receipt unparseable {exc}")
        raise SystemExit(1)
    if not isinstance(doc, dict):
        print("FAILED:IMP-0081-probe1 receipt not an object")
        raise SystemExit(1)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0081-probe1 self-declared {st}")
        raise SystemExit(1)
    if "SUCCESS:IMP-0081" not in text:
        print("FAILED:IMP-0081-probe1 sentinel absent")
        raise SystemExit(1)
    return doc


def main() -> int:
    _require_receipt()
    with tempfile.TemporaryDirectory(prefix="imp0081-p1-") as tmp:
        root = Path(tmp) / "upstream"
        planted = init_local_git_repo(root, "IMP-0081 probe1 planted\n")
        independent = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        if independent.lower() != planted.lower():
            print(
                f"FAILED:IMP-0081-probe1 independent rev-parse {independent} "
                f"!= planted {planted}"
            )
            return 1
        url = root.resolve().as_uri()
        rec = map_identity(
            "planted-pkg",
            url,
            recorded_commit=planted,
            resolver=GitLsRemoteResolver(timeout_seconds=15),
            sleeper=lambda _s: None,
        )
        if rec.status != STATUS_VERIFIED:
            print(f"FAILED:IMP-0081-probe1 mapper status={rec.status}")
            print(json.dumps(rec.to_dict(), indent=2)[:2000])
            return 1
        if rec.resolved_commit != planted.lower():
            print(
                f"FAILED:IMP-0081-probe1 resolved {rec.resolved_commit} "
                f"!= planted {planted}"
            )
            return 1
        if rec.first_party:
            print("FAILED:IMP-0081-probe1 git-sourced marked first_party")
            return 1
        payload = {
            "independent_rev_parse": independent.lower(),
            "mapped_status": rec.status,
            "mapped_commit": rec.resolved_commit,
            "pass": True,
            "planted_head": planted.lower(),
            "probe": "probe1-verified-mapping",
            "signals_agree": True,
            "unit_id": "IMP-0081",
            "url": url,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            "signal1_mapper=VERIFIED "
            f"signal2_rev_parse={independent.lower()[:12]} "
            "signals_agree=True"
        )
        print("SUCCESS:IMP-0081-probe1 verified mapping; independent rev-parse matches")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
