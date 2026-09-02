#!/usr/bin/env python3
"""Write LF canonical fixture JSON, plus one CRLF twin of all-kinds."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "tools" / "agentspec"))
sys.path.insert(0, str(HERE))

from agentspec.canonical import export  # noqa: E402
from scenario import FIXTURES  # noqa: E402

FIXDIR = HERE / "fixtures"


def main() -> int:
    FIXDIR.mkdir(parents=True, exist_ok=True)
    for name, wf in FIXTURES.items():
        path = FIXDIR / f"{name}.json"
        path.write_bytes(export(wf))
        print(f"wrote {path.relative_to(HERE.parents[3])} {path.stat().st_size}B LF")
    all_lf = export(FIXTURES["all-kinds"])
    crlf_path = FIXDIR / "all-kinds.crlf.json"
    crlf_path.write_bytes(all_lf.replace(b"\n", b"\r\n"))
    print(f"wrote {crlf_path.name} {crlf_path.stat().st_size}B CRLF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
