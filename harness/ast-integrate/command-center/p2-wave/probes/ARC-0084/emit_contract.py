"""Write command-center/phase4/contracts/ARC-0084.json from live floors."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from floors import derive
from schema_build import build

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center" / "phase4" / "contracts" / "ARC-0084.json"


def write() -> dict:
    derivation = derive()
    floors = derivation["floors"]
    doc = build(floors, derivation)
    Draft202012Validator.check_schema(doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return doc


def main() -> int:
    doc = write()
    print(
        f"wrote {OUT.relative_to(REPO).as_posix()} "
        f"floors={doc['size_floors']} sentinel={doc['sentinel']}"
    )
    print("SUCCESS:ARC-0084 contract emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
