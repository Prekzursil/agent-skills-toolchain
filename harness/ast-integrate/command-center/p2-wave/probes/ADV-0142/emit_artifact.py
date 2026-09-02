#!/usr/bin/env python3
"""Emit ADV-0142 re-identification assessment."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402


def main() -> int:
    doc = E.build_document()
    out = REPO / E.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    out.write_text(text, encoding="utf-8")
    sha, n = E.digest_file(out)
    print(f"wrote {E.OUT_REL} bytes={n} sha256={sha}")
    print(
        "joins={successful_joins} ids={successful_identifications} "
        "files={publishable_files}".format(**doc["counts"])
    )
    print(doc["sentinel"][:80] + "...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
