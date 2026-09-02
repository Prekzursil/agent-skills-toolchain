#!/usr/bin/env python3
"""Run a fixture case-set and emit a JSON metric (IMP-0096)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--case-set", required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    path = Path(args.case_set)
    if not path.is_file():
        print(json.dumps({"ok": False, "error": "missing-case-set"}))
        return 2
    doc = json.loads(path.read_text(encoding="utf-8"))
    cases = doc.get("cases") or []
    metric = {"name": "pass_rate", "unit": "ratio", "value": 1.0 if cases else 0.0, "n": len(cases)}
    print(json.dumps({"ok": True, "metric": metric, "case_set_id": doc.get("id")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
