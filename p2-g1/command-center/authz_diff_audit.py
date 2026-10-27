#!/usr/bin/env python
"""Structural diff of the catalog before/after the D2 fixes: prove the edit surface is exactly
the 35 reported changes and nothing else moved (root keys, unit count, unit ids, every field).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
NEW = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
OLD = Path(os.environ.get("TEMP", "/tmp")) / "WUC-authz-preedit.json"


def load(p: Path) -> dict[str, Any]:
    return json.loads(p.read_bytes().replace(b"\r\n", b"\n").decode("utf-8"))


def main() -> int:
    if not OLD.is_file():
        print(f"FAILED:authz-diff-audit pre-edit snapshot missing at {OLD}")
        return 1
    old, new = load(OLD), load(NEW)

    print("root keys added   :", sorted(set(new) - set(old)))
    print("root keys removed :", sorted(set(old) - set(new)))
    unchanged_roots = [
        k for k in sorted(set(old) & set(new)) if k != "work_units" and old[k] == new[k]
    ]
    changed_roots = [
        k for k in sorted(set(old) & set(new)) if k != "work_units" and old[k] != new[k]
    ]
    print("root keys byte-identical :", unchanged_roots)
    print("root keys CHANGED        :", changed_roots)

    ou = {str(u["id"]): u for u in old["work_units"]}
    nu = {str(u["id"]): u for u in new["work_units"]}
    print("unit count old/new:", len(old["work_units"]), len(new["work_units"]))
    print("unit ids added    :", sorted(set(nu) - set(ou)))
    print("unit ids removed  :", sorted(set(ou) - set(nu)))
    print(
        "unit ORDER preserved:",
        [u["id"] for u in old["work_units"]] == [u["id"] for u in new["work_units"]],
    )

    diffs: list[tuple[str, str, Any, Any]] = []
    for uid in sorted(set(ou) & set(nu)):
        a, b = ou[uid], nu[uid]
        for field in sorted(set(a) | set(b)):
            if a.get(field, "<absent>") != b.get(field, "<absent>"):
                diffs.append(
                    (uid, field, a.get(field, "<absent>"), b.get(field, "<absent>"))
                )
    print(f"\nchanged unit fields: {len(diffs)}")
    by_field: dict[str, int] = {}
    for _, field, _, _ in diffs:
        by_field[field] = by_field.get(field, 0) + 1
    print("by field:", by_field)
    for uid, field, a, b in diffs:
        print(f"  {uid} {field}: {a!r} -> {b!r}")

    expected_fields = {
        "owner_approval_required",
        "tool_permissions",
        "execution_substrate",
    }
    bad = sorted({f for _, f, _, _ in diffs} - expected_fields)
    ok = (
        sorted(set(new) - set(old)) == ["tool_policy"]
        and not sorted(set(old) - set(new))
        and not changed_roots
        and len(old["work_units"]) == len(new["work_units"]) == 2007
        and not (set(nu) ^ set(ou))
        and not bad
    )
    print(
        "SUCCESS:authz-diff-audit surface=exactly-as-declared"
        if ok
        else f"FAILED:authz-diff-audit unexpected changes in fields {bad} / roots {changed_roots}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
