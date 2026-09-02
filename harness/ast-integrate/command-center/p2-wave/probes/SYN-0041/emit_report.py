#!/usr/bin/env python3
"""Run the SYN-0019-style gate, then write SYN-0041.final-report.json."""
from __future__ import annotations

import time
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from gate import GATE_RECEIPT_REL, GateBlocked, authorize_write  # noqa: E402
from generate import OUT_REL, build_report, dumps, payload, validate_schema  # noqa: E402


def emit(root: Path, *, now: float | None = None, rerun: bool = True, out_rel: str | None = None) -> int:
    now = time.time() if now is None else now
    out_rel = out_rel or OUT_REL
    try:
        authorize_write(root, now, rerun=rerun, receipt_path=root / GATE_RECEIPT_REL)
    except GateBlocked as exc:
        print(f"FAILED:SYN-0041 {exc.reason}")
        return 1
    doc = build_report(root)
    validate_schema(root, doc)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:SYN-0041 self-declared {doc.get('state')}")
        return 1
    body = payload(doc)
    counts = body["label_counts"]
    total = int(body["item_total"])
    if sum(counts.values()) != total:
        print(f"FAILED:SYN-0041 count-mismatch counts={counts} total={total}")
        return 1
    sentinel = str(doc.get("sentinel") or body.get("completion_sentinel") or "")
    text = dumps(doc)
    if sentinel not in text:
        print("FAILED:SYN-0041 completion_sentinel absent from serialized report")
        return 1
    dest = root / out_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    print(f"wrote {out_rel} bytes={len(text.encode('utf-8'))}")
    print(f"label_counts={counts} item_total={total}")
    print("SUCCESS:SYN-0041")
    return 0


def main() -> int:
    return emit(REPO)


if __name__ == "__main__":
    raise SystemExit(main())
