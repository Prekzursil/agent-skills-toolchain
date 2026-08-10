"""P13 blind-spot survey: catalog structure + option IDs + register instances.

Read-only. Prints a structural census so downstream measurement is grounded.
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
CC = REPO / "command-center"


def jload(p: pathlib.Path):
    return json.loads(p.read_text(encoding="utf-8"))


def describe(name: str, obj, depth: int = 0, maxdepth: int = 2) -> None:
    pad = "  " * depth
    if isinstance(obj, dict):
        print(f"{pad}{name}: dict[{len(obj)}] keys={list(obj)[:14]}")
        if depth < maxdepth:
            for k, v in list(obj.items())[:14]:
                describe(k, v, depth + 1, maxdepth)
    elif isinstance(obj, list):
        print(f"{pad}{name}: list[{len(obj)}]")
        if obj and depth < maxdepth:
            describe("[0]", obj[0], depth + 1, maxdepth)
    else:
        s = str(obj)
        print(f"{pad}{name}: {type(obj).__name__} = {s[:90]}")


def main() -> int:
    print("=" * 70)
    print("WORK-UNIT-CATALOG.json")
    print("=" * 70)
    cat = jload(CC / "WORK-UNIT-CATALOG.json")
    describe("root", cat, maxdepth=2)

    print()
    print("=" * 70)
    print("OPTION-ID-RESOLUTION.json")
    print("=" * 70)
    opt = jload(CC / "OPTION-ID-RESOLUTION.json")
    describe("root", opt, maxdepth=2)

    print()
    print("=" * 70)
    print("register schema instances present?")
    print("=" * 70)
    for sch in sorted((CC / "schema").glob("*register*.schema.json")):
        print(f"  schema: {sch.name}")
    print("  --- candidate instances in command-center ---")
    for p in sorted(CC.glob("*.json")):
        if "register" in p.name.lower() or "REGISTER" in p.name:
            print(f"  instance json: {p.name}")
    for p in sorted(CC.glob("*.md")):
        if "register" in p.name.lower() or "REGISTER" in p.name:
            print(f"  instance md:   {p.name}")

    print()
    print("=" * 70)
    print("ARTIFACT-MANIFEST.json")
    print("=" * 70)
    man = jload(CC / "ARTIFACT-MANIFEST.json")
    describe("root", man, maxdepth=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
