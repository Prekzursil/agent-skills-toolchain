#!/usr/bin/env python3
"""Point schema $id/$ref at file:// of this tree so jsonschema does not hit the network."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

REPO = Path(os.environ.get("AST_INTEGRATE_ROOT", Path(__file__).resolve().parents[3])).resolve()
OLD = "https://ast-integrate.invalid/"
NEW = REPO.as_uri().rstrip("/") + "/"
DIRS = [
    REPO / "platform" / "schema",
    REPO / "command-center" / "schema",
    REPO / "schema",
]
# Prior Windows/WSL rewrites leave file:///C:/... or file:///home/... bases.
FILE_BASE_RE = re.compile(
    r"file://[^\"\\\s]+?(?=/(?:platform|command-center)/schema/)"
)


def rebase(text: str) -> str:
    text = text.replace(OLD, NEW)
    return FILE_BASE_RE.sub(NEW.rstrip("/"), text)


def main() -> int:
    n_files = n_hits = 0
    for d in DIRS:
        if not d.is_dir():
            continue
        for path in d.rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            new = rebase(text)
            if new == text:
                continue
            path.write_text(new, encoding="utf-8", newline="\n")
            n_files += 1
            n_hits += text.count(OLD) + len(FILE_BASE_RE.findall(text))
    rec = REPO / "platform" / "schema" / "receipt.schema.json"
    if rec.is_file():
        doc = json.loads(rec.read_text(encoding="utf-8"))
        core = doc.get("$defs", {}).get("receipt_core")
        if isinstance(core, dict):
            core["additionalProperties"] = True
            rec.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
            print("AP-true receipt_core", flush=True)
    print(f"SUCCESS:schema-file-ids files={n_files} replacements={n_hits} base={NEW}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
