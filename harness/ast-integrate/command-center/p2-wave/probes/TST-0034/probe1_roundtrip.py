#!/usr/bin/env python3
"""Probe 1: marketplace.json round-trips byte-identically through the registry reader.

Independent of probe 2 (does not census unresolved source paths). Both-states:
canonical encoding passes; a compact encoding of the same object fails dump(load).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.manifest_reader import (  # noqa: E402
    RULE_ROUND_TRIP,
    canonical_live_document,
    check_manifest,
    dump_bytes,
    ensure_live_subject,
    live_path,
    load_manifest,
)

ART = REPO / "command-center/receipts/TST-0034.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def _write(root: Path, data: dict, compact: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    mp = root / "marketplace.json"
    if compact:
        mp.write_bytes(
            json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        )
    else:
        mp.write_bytes(dump_bytes(data))
    from marketplace.manifest_reader import canonical_plugin_document

    (root / "plugin.json").write_bytes(dump_bytes(canonical_plugin_document()))
    return mp


def main() -> int:
    live = ensure_live_subject(REPO)
    loaded = load_manifest(live)
    dumped = dump_bytes(loaded.data)
    live_rt = dumped == loaded.raw
    live_report = check_manifest(live, REPO)
    print(
        f"live_path={live_path(REPO).relative_to(REPO).as_posix()} "
        f"round_trip={live_rt} dump_bytes={len(dumped)} raw_bytes={len(loaded.raw)}"
    )
    if not live_rt:
        print("FAILED:TST-0034-probe1 live dump(load) is not byte-identical")
        return 1
    if not live_report.ok:
        print("FAILED:TST-0034-probe1 live report not ok", live_report.findings)
        return 1

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        clean = _write(base / "clean", canonical_live_document(), compact=False)
        compact = _write(base / "compact", canonical_live_document(), compact=True)
        c = check_manifest(clean, REPO)
        m = check_manifest(compact, REPO)
        print(
            f"both_states clean_ok={c.ok} compact_ok={m.ok} "
            f"compact_rules={sorted({f.rule for f in m.findings})}"
        )
        if not c.ok:
            print("FAILED:TST-0034-probe1 clean canonical fixture failed", c.findings)
            return 1
        if m.ok:
            print("FAILED:TST-0034-probe1 compact mutant did not fail")
            return 1
        if RULE_ROUND_TRIP not in {f.rule for f in m.findings}:
            print("FAILED:TST-0034-probe1 compact mutant missed round-trip rule")
            return 1
        if c.round_trip is not True or m.round_trip is not False:
            print("FAILED:TST-0034-probe1 round_trip flags", c.round_trip, m.round_trip)
            return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if doc.get("unit_id") != "TST-0034":
            print("FAILED:TST-0034-probe1 unit_id", doc.get("unit_id"))
            return 1
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            print("FAILED:TST-0034-probe1 self-declared", doc.get("state"))
            return 1
        if "SUCCESS:TST-0034" not in text:
            print("FAILED:TST-0034-probe1 sentinel absent")
            return 1
        rt = (doc.get("round_trip") or {}).get("byte_identical")
        if rt is not True:
            print("FAILED:TST-0034-probe1 artifact round_trip.byte_identical", rt)
            return 1

    print("SUCCESS:TST-0034-probe1 live byte-identical round-trip; compact mutant fails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
