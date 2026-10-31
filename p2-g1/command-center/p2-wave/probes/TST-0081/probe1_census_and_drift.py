#!/usr/bin/env python3
"""TST-0081 probe1: package census re-derivation + live drift audit.

Re-derives the receipt's recorded census internally (14 entries, byte
sum, ceiling arithmetic) and re-runs the LIVE allowlisted census with
the estate gate module. The live tree has moved since the receipt was
written (recorded shas no longer match the current files); the probe
asserts the receipt's census is internally consistent and IDENTIFIES
the measured bytes, quantifies the drift, and records the live census -
honesty over optics."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import package_hygiene as ph  # noqa: E402

UNIT = "TST-0081"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= 4096, "under-min-bytes", str(OUT.stat().st_size))
    chk(str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "self-declared")
    chk("SUCCESS:TST-0081" in text, "sentinel-absent")

    cp = doc.get("current_package") or {}
    entries = cp.get("entries") or []
    chk(len(entries) == 14, "recorded-entry-count", str(len(entries)))
    total = sum(int(e.get("uncompressed_bytes", 0)) for e in entries)
    chk(total == 97075, "recorded-byte-sum", str(total))
    impl = doc.get("implementation") or {}
    chk(int(impl.get("size_ceiling_bytes", 0)) == 10485760, "recorded-ceiling")
    headroom = 10485760 - total
    ans = str(doc.get("answer") or "")
    chk(str(headroom) in ans, "headroom-arithmetic", "derived=" + str(headroom))
    chk(all(e.get("path") and e.get("sha256") for e in entries), "entries-well-formed")
    # drift quantification: which recorded entries still match live bytes
    same = missing = drifted = 0
    for e in entries:
        f = REPO / str(e["path"])
        if not f.is_file():
            missing += 1
            continue
        raw = f.read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(raw).hexdigest() == e["sha256"]:
            same += 1
        else:
            drifted += 1
    chk(same + drifted + missing == 14, "drift-census-complete")
    # live census mechanics with the estate gate module
    packed = ph.pack_current_worktree(REPO)
    live_n = packed.file_count
    live_b = packed.total_uncompressed_bytes
    chk(packed.ok is True and not packed.findings, "live-gate-green")
    chk(live_n == len(packed.members), "live-count-consistent", str(live_n))
    chk(live_b == sum(m.size for m in packed.members), "live-bytes-consistent")
    chk(packed.headroom_bytes == packed.size_ceiling_bytes - live_b, "live-headroom-math")
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails))
        return 1
    print(json.dumps({"recorded": {"entries": 14, "bytes": 97075, "ceiling": 10485760, "headroom": headroom,
                                  "internal_consistency": "PASS"},
                      "drift_since_measurement": {"unchanged": same, "drifted": drifted, "absent": missing},
                      "live_census_now": {"files": live_n, "bytes": live_b,
                                          "ceiling": packed.size_ceiling_bytes,
                                          "headroom": packed.headroom_bytes,
                                          "digest": packed.integrity_digest}}, indent=1))
    print("SUCCESS:" + UNIT + "-probe1 recorded census internally consistent (14 entries, 97075 bytes, headroom " + str(headroom) + "); drift quantified (" + str(drifted) + " drifted, " + str(missing) + " absent - tree moved after measurement, disclosed not asserted); live gate census green and self-consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
