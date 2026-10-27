#!/usr/bin/env python3
"""BLD-0016 probe1: planted existence-classification controls.

The unit asks which Final-Deliverables item has no artifact on disk. The
receipt's finding: all 29 items resolved ABSENT (no concrete path bound, so
none may claim PRESENT). Controls recorded by the receipt: nonexistent path ->
ABSENT; zero-byte file -> EMPTY, never PRESENT; directory -> requires a named
minimum member. This probe rebuilds that classifier, proves each control on
planted fixtures, and re-verifies the receipt's all-ABSENT answer set is
internally consistent and still true live.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import REPO, ProbeFailure, check_receipt_core, require  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
UID = "BLD-0016"


def ensure_fixtures() -> dict[str, Path]:
    FIX.mkdir(parents=True, exist_ok=True)
    (FIX / "dir_with_member").mkdir(exist_ok=True)
    made: dict[str, Path] = {}
    made["absent"] = FIX / "does-not-exist.bin"  # intentionally never created
    (FIX / "empty.bin").write_bytes(b"")  # 0 bytes: emptiness is the point
    made["empty"] = FIX / "empty.bin"
    member = FIX / "dir_with_member" / "member.txt"
    member.write_text("BLD-0016 fixture member\n", encoding="utf-8")
    made["member"] = member
    made["dir_with_member"] = FIX / "dir_with_member"
    d2 = FIX / "dir_without_member"
    d2.mkdir(exist_ok=True)
    made["dir_without_member"] = d2
    return made


def classify(path: Path, min_member: str | None = None) -> dict:
    """Existence classification with fresh, filesystem-read digests."""
    if not path.exists():
        return {"verdict": "ABSENT", "bytes": None, "sha256": None}
    if path.is_file():
        raw = path.read_bytes()
        if len(raw) == 0:
            return {"verdict": "EMPTY", "bytes": 0, "sha256": None}
        return {"verdict": "PRESENT", "bytes": len(raw),
                "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()}
    if path.is_dir():
        member = path / min_member if min_member else None
        if min_member is None or not (member and member.is_file()):
            return {"verdict": "DIR-INCOMPLETE", "bytes": None, "sha256": None}
        raw = (path / min_member).read_bytes()
        return {"verdict": "PRESENT", "bytes": len(raw),
                "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
                "member": min_member}
    return {"verdict": "ABSENT", "bytes": None, "sha256": None}


def main() -> int:
    doc = check_receipt_core(UID)
    fx = ensure_fixtures()

    # --- the receipt's three planted controls -------------------------------
    a = classify(fx["absent"])
    require(a["verdict"] == "ABSENT", f"nonexistent path classified {a}")
    e = classify(fx["empty"])
    require(e["verdict"] == "EMPTY" and e["bytes"] == 0,
            f"zero-byte file classified {e} (must be EMPTY, never PRESENT)")
    d = classify(fx["dir_without_member"], min_member="required.txt")
    require(d["verdict"] == "DIR-INCOMPLETE",
            f"directory without named member classified {d}")
    m = classify(fx["dir_with_member"], min_member="member.txt")
    require(m["verdict"] == "PRESENT" and m["bytes"] > 0 and m["sha256"],
            f"directory+member classified {m}")

    # --- digest must be read fresh from bytes, never copied -----------------
    actual = hashlib.sha256(
        fx["member"].read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    require(actual == m["sha256"], "digest not reproducible from filesystem bytes")
    require(m["sha256"] != "0" * 64, "digest guard failed (impossible)")

    # --- the receipt's answer set: all items, no unbound PRESENTs -----------
    dp = doc.get("deliverable_probe") or {}
    items = dp.get("items") or []
    require(dp.get("item_count") == len(items), "item_count != len(items)")
    absent_ids = [str(x) for x in (dp.get("absent") or [])]
    present_ids = [str(x) for x in (dp.get("present") or [])]
    empty_ids = [str(x) for x in (dp.get("empty") or [])]
    dirinc_ids = [str(x) for x in (dp.get("dir_incomplete") or [])]
    require(len(absent_ids) + len(present_ids) + len(empty_ids) + len(dirinc_ids)
            == len(items), "verdict id lists do not partition the items")
    require(not present_ids and not empty_ids and not dirinc_ids,
            "receipt no longer the all-ABSENT answer this probe verifies")
    unbound = sum(1 for it in items
                  if it.get("resolved_path") is None
                  and not (it.get("candidate_paths") or []))
    require(unbound == len(items),
            f"{len(items) - unbound} items have bound paths; probe scope is the unbound-answer receipt")

    # live truthfulness: no item's candidates exist on this tree
    live_present = 0
    for it in items:
        for rel in it.get("candidate_paths") or []:
            if (REPO / str(rel)).exists():
                live_present += 1
    require(live_present == 0,
            f"{live_present} receipt candidates now exist live; receipt answer stale")

    # controls recorded by the receipt re-fire here
    ctl = {str(c.get("id")): c for c in (doc.get("controls") or [])}
    require(ctl.get("manifest-nonexistent-path-absent", {}).get("pass") is True,
            "receipt control manifest-nonexistent-path-absent not recorded PASS")
    ctl_planted = classify(FIX / "does-not-exist.bin")
    require(ctl_planted["verdict"] == "ABSENT",
            "receipt-recorded control does not reproduce on planted fixture")

    print(json.dumps({
        "probe": "probe1-planted-controls", "unit_id": UID,
        "controls_fired": ["absent->ABSENT", "zero-byte->EMPTY",
                           "dir-no-member->DIR-INCOMPLETE", "dir+member->PRESENT",
                           "digest-fresh-not-copied"],
        "receipt_items": len(items), "absent": len(absent_ids),
        "unbound_items": unbound, "live_candidates_existing": live_present,
        "pass": True,
    }, ensure_ascii=False))
    print(f"SUCCESS:{UID}-probe1 planted controls fire; all {len(items)} "
          f"receipt items remain unbound-ABSENT live")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe1 {exc}")
        raise SystemExit(1)
