#!/usr/bin/env python3
"""Emit command-center/phase3/SALVAGE-REGISTER.json for ARC-0075."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import salvage as S  # noqa: E402
import schema_local as SL  # noqa: E402


def main() -> int:
    schema_path = S.REPO / S.SCHEMA_REL
    if not schema_path.is_file():
        print(f"FAILED:ARC-0075 schema missing {S.SCHEMA_REL}")
        return 1
    empty_rejected, _, _ = SL.reject_empty_accept_live({})
    if not empty_rejected:
        print("FAILED:ARC-0075 schema accepted empty garbage")
        return 1
    doc = S.build()
    empty_rejected, live_ok, live_errs = SL.reject_empty_accept_live(doc)
    if not empty_rejected:
        print("FAILED:ARC-0075 schema accepted empty garbage")
        return 1
    if not live_ok:
        print("FAILED:ARC-0075 live artifact schema-invalid")
        for err in live_errs[:20]:
            print(" ", err)
        return 1
    out = S.REPO / S.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(S.dump(doc), encoding="utf-8")
    print(f"wrote {S.OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:ARC-0075 salvage register emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
