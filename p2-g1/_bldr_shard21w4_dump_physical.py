"""Dump physical schema fragment for my units."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
from schema_resolver import resolve, load_registry  # noqa: E402

UNITS = [
    "WFA-0065", "WFA-0069", "WFA-0070", "WFA-0074",
    "WFA-0084", "WFA-0085", "WFA-0086", "WFA-0094",
    "WFA-0106", "WFA-0110", "WFA-0113",
]


def frag_props(doc: dict, frag: str | None) -> None:
    if frag and frag.startswith("#/$defs/"):
        name = frag.split("/")[-1]
        sub = (doc.get("$defs") or {}).get(name) or {}
    else:
        sub = doc
    props = sub.get("properties", {})
    print("  top allow:", sorted(props.keys()))
    print("  required:", sub.get("required"))
    print("  additionalProperties:", sub.get("additionalProperties", "unset"))
    for key in ("artifacts", "evidence", "reviewer", "tests", "negative_controls", "probes"):
        node = props.get(key)
        if not isinstance(node, dict):
            continue
        items = node.get("items", {})
        if items:
            print(f"  {key}.items props:", sorted((items.get("properties") or {}).keys()),
                  "req:", items.get("required"))
            role = (items.get("properties") or {}).get("role", {})
            if role.get("enum"):
                print(f"  {key}.items.role enum:", role["enum"])
        else:
            print(f"  {key} props:", sorted((node.get("properties") or {}).keys()),
                  "req:", node.get("required"))


def main() -> int:
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    entries = {u["id"]: u for u in cat["work_units"] if u.get("id") in UNITS}
    reg = load_registry()
    seen: set[tuple[str, str | None]] = set()
    for uid in UNITS:
        e = entries[uid]
        r = resolve(e["output_schema"], reg)
        key = (r.physical_path, r.physical_fragment)
        print("=" * 15, uid, "->", r.physical_path, r.physical_fragment, "class:", r.artifact_class)
        if key in seen:
            print("  (same as previous, skipped)")
            continue
        seen.add(key)
        doc = json.loads((REPO / r.physical_path).read_text(encoding="utf-8"))
        frag_props(doc, r.physical_fragment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
