#!/usr/bin/env python3
"""BLD-0032 probe2: reviewer hand-trace of evidence anchors.

Rebuilds the control packet (probe1's builder), then hand-traces the
receipt's evidence citations: cited line numbers land on the heading the
claim names (unqualified / [UNVERIFIED]-qualified / ungrounded), and
CLAIM-REGISTRY citations name real claim ids with matching statuses.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import ProbeFailure, check_receipt_core, require  # noqa: E402

UID = "BLD-0032"
HERE = Path(__file__).resolve().parent
PACK = HERE / "fixtures" / "control-packet"


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "bld0032p1", HERE / "probe1_controls.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def anchor_name(anchor: str) -> str:
    """'.../decision-packet.md:5' -> 'decision-packet.md' (line suffix off)."""
    return Path(anchor.rsplit(":", 1)[0].replace("\\", "/")).name


def main() -> int:
    doc = check_receipt_core(UID)
    b = load_builder()
    b.build_packet()
    statuses = b.parse_registry()

    packet = PACK / "decision-packet.md"
    require(packet.is_file(), "packet fixture missing after rebuild")
    lines = packet.read_text(encoding="utf-8").splitlines()

    ev = doc.get("evidence") or []
    require(len(ev) >= 6, f"evidence rows shrank: {len(ev)}")
    traced = 0
    for e in ev:
        claim = str(e.get("claim") or "")
        # 2026-10-26 envelope repair: the receipt profile (platform/schema/
        # receipt.schema.json evidence_item additionalProperties: false) forbids
        # a bare `line` key, so the cited line moved into the profile-legal
        # `anchor` ("path:line"). Read it from either location; the check is
        # unchanged - the cited line must still land on the named heading.
        line_no = e.get("line")
        if not line_no:
            suffix = str(e.get("anchor") or "").rsplit(":", 1)[-1]
            line_no = int(suffix) if suffix.isdigit() else None
        if not line_no:
            continue
        name = anchor_name(str(e.get("anchor") or ""))
        if name == "decision-packet.md":
            require(0 < int(line_no) <= len(lines),
                    f"cited line {line_no} outside packet ({len(lines)} lines)")
            cited = lines[int(line_no) - 1]
            low = claim.lower()
            if "unqualified" in low:
                require(cited.startswith("## ") and not b.TAG_RE.search(cited),
                        f"line {line_no} not an unqualified heading: {cited!r}")
                traced += 1
            elif "carries unverified" in low:
                require("[UNVERIFIED]" in cited,
                        f"line {line_no} lacks [UNVERIFIED]: {cited!r}")
                traced += 1
            elif "no traceable premise" in low:
                require(cited.startswith("## Paint"),
                        f"line {line_no} not the ungrounded heading: {cited!r}")
                traced += 1
        elif name == "CLAIM-REGISTRY.json":
            ids = [cid for cid in statuses if cid in claim]
            require(ids, f"registry citation names no known claim: {claim!r}")
            want = "UNVERIFIED" if "UNVERIFIED" in claim else "NOT-CHECKED"
            for cid in ids:
                require(statuses[cid] == want,
                        f"{cid} status {statuses[cid]} != {want}")
            traced += 1
    require(traced >= 5, f"hand-trace covered only {traced} rows")

    print(json.dumps({
        "probe": "probe2-reviewer-hand-trace", "unit_id": UID,
        "evidence_rows": len(ev), "hand_traced": traced, "pass": True,
    }, ensure_ascii=False))
    print(f"SUCCESS:{UID}-probe2 citations land on cited lines and support "
          f"their claims")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe2 {exc}")
        raise SystemExit(1)
