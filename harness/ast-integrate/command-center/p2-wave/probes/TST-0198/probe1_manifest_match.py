#!/usr/bin/env python3
"""Named probe 1: per-file manifest match (catalog evidence signal a).

Live NFD tree vs NFC manifest. ASCII both-states control must match
trivially (including byte equality). Composed names must match only after
the declared NFC normalisation. Round-trip onto NFC dest paths must lose
no file. Receipt claims must match this live run.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from matcher import CHOSEN_FORM, live_campaign  # noqa: E402

ART = REPO / "command-center/receipts/TST-0198.json"


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0198-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return _fail("receipt missing or tiny")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0198" not in text:
        return _fail("sentinel absent")
    if doc.get("unit_id") != "TST-0198":
        return _fail(f"unit_id={doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared:{st}")
    if doc.get("chosen_normal_form") != CHOSEN_FORM:
        return _fail(f"chosen_normal_form={doc.get('chosen_normal_form')}")

    with tempfile.TemporaryDirectory(prefix="tst0198-p1-") as tmp:
        live = live_campaign(Path(tmp))

    if not live["ok"]:
        print(json.dumps({k: live[k] for k in ("ok", "all_matched", "ascii_trivial_match", "nfd_byte_equality_fails", "nfd_nfc_match")}, indent=2))
        return _fail("live campaign not ok")
    if not live["all_matched"]:
        return _fail("not all files matched")
    if not live["ascii_trivial_match"]:
        return _fail("ASCII both-states control failed")
    if not live["nfd_nfc_match"]:
        return _fail("NFD names did not match NFC manifest")
    if not live["round_trip"]["no_file_lost"]:
        return _fail(f"round-trip lost files {live['round_trip']}")
    if live["round_trip"]["source_count"] != 3:
        return _fail(f"source_count={live['round_trip']['source_count']}")

    rec_files = doc.get("per_file_matches") or []
    if len(rec_files) != 3:
        return _fail(f"receipt per_file_matches={len(rec_files)}")
    rec_kinds = sorted(r.get("kind") for r in rec_files)
    live_kinds = sorted(r.get("kind") for r in live["per_file"])
    if rec_kinds != live_kinds:
        return _fail(f"kind drift receipt={rec_kinds} live={live_kinds}")
    for row in rec_files:
        if not row.get("matched"):
            return _fail(f"receipt unmatched {row}")
        if row.get("form") != CHOSEN_FORM:
            return _fail(f"receipt form {row.get('form')}")

    summary = {
        "probe": "probe1-manifest-match",
        "unit_id": "TST-0198",
        "pass": True,
        "chosen_form": CHOSEN_FORM,
        "files_checked": len(live["per_file"]),
        "all_matched": True,
        "ascii_trivial": True,
        "round_trip_no_loss": True,
        "source_count": live["round_trip"]["source_count"],
        "dest_count": live["round_trip"]["dest_count"],
    }
    print(json.dumps(summary, sort_keys=True))
    for row in live["per_file"]:
        print(
            f"file kind={row['kind']} matched={row['matched']} "
            f"byte_equal={row['byte_equal']} form={row['form']}"
        )
    print("SUCCESS:TST-0198-probe1 per-file NFC manifest match and round-trip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
