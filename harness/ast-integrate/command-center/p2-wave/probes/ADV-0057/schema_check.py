#!/usr/bin/env python3
"""Downstream consumer: parse + schema-validate the ADV-0057 catalog artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from schema_local import garbage_accepted, schema_errors  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0057-governance-policy-legal-coherence.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0057-schema-check artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    bad = garbage_accepted()
    if bad:
        print(f"FAILED:ADV-0057-schema-check schema accepted garbage {bad[:1]}")
        return 1
    errs = schema_errors(doc)
    if errs:
        print("FAILED:ADV-0057-schema-check")
        for line in errs[:20]:
            print(" ", line)
        return 1
    print(
        "consumer=json.loads + license-and-rights-record RefResolver\n"
        f"unit_id={doc.get('unit_id')}\n"
        f"state={doc.get('state')}\n"
        "SUCCESS:consumer-read"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
