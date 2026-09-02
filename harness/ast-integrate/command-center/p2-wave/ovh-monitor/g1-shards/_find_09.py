#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

DOC = Path(
    r"C:\Users\Prekzursil\source\ast-integrate\command-center\adversarial"
    r"\ADV-0005-p0-p1-fresh-context-rederivation.json"
)


def walk(obj, path="$"):
    if obj == 0.9 or obj == 0.90:
        print("HIT", path, repr(obj), type(obj).__name__)
    if isinstance(obj, dict):
        for k, v in obj.items():
            walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, f"{path}[{i}]")


def main() -> None:
    doc = json.loads(DOC.read_text(encoding="utf-8"))
    walk(doc)
    print("top_keys", sorted(doc))
    print("has_evidence", "evidence" in doc)
    if "evidence" in doc:
        print("evidence0", json.dumps(doc["evidence"][0] if doc["evidence"] else {}, indent=2)[:500])


if __name__ == "__main__":
    main()
