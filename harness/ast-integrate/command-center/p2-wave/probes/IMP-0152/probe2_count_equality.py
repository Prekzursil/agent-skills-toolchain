#!/usr/bin/env python3
"""Named probe 2: candidate count == registry entry count (computed equality).

Counts are derived from the same raw_entry_rows() sequence the adapter walks.
A drop-last mutant must make equality fail (detector fires on the broken state).
A packages-shaped rewrite of the same index must keep equality (shape invariance).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import adapter  # noqa: E402


def _required_fields(c: dict) -> bool:
    ident = c.get("package_identity") or {}
    return all(
        [
            ident.get("id") or c.get("package_id"),
            c.get("version") is not None,
            c.get("channel") is not None,
            isinstance(c.get("permissions"), list),
            c.get("description_quoted"),
            c.get("untrusted") is True,
        ]
    )


def main() -> int:
    loaded = adapter.discover_from_path()
    doc = loaded["doc"]
    entry_count = adapter.registry_entry_count(doc)
    candidates = loaded["candidates"]
    cand_count = len(candidates)
    equal = entry_count == cand_count
    fields_ok = all(_required_fields(c) for c in candidates) if candidates else False

    dropped = adapter.drop_last(candidates)
    drop_equal = len(dropped) == entry_count
    fired_on_drop = (not drop_equal) and equal and cand_count >= 1

    nested = adapter.entries_as_packages_doc(doc)
    nested_count = adapter.registry_entry_count(nested)
    nested_cands = adapter.discover(nested)
    nested_equal = nested_count == len(nested_cands) == entry_count

    # Distinct identities: (id, version, channel) from the fixture entries
    # must all appear — no collapse of hello-skill 1.0.0 with 1.1.0.
    keys = {
        (c["package_id"], c["version"], c["channel"]) for c in candidates
    }
    raw_keys = []
    for row in adapter.raw_entry_rows(doc):
        if isinstance(row, dict):
            raw_keys.append(
                (
                    adapter._entry_id(row) or "",
                    str(row.get("version") or "0.0.0"),
                    str(row.get("channel") or "stable"),
                )
            )
    key_equal = set(raw_keys) == keys and len(raw_keys) == len(keys)

    out = {
        "probe": "probe2-count-equality",
        "unit_id": "IMP-0152",
        "registry_source": loaded["registry_source"],
        "registry_entry_count": entry_count,
        "candidate_count": cand_count,
        "equal": equal,
        "required_fields_on_all": fields_ok,
        "drop_last_count": len(dropped),
        "drop_last_still_equal": drop_equal,
        "fired_on_drop": fired_on_drop,
        "nested_entry_count": nested_count,
        "nested_candidate_count": len(nested_cands),
        "nested_equal": nested_equal,
        "identity_set_equal": key_equal,
        "pass": bool(
            equal
            and fields_ok
            and fired_on_drop
            and nested_equal
            and key_equal
            and entry_count >= 5
        ),
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"entries={entry_count} candidates={cand_count} equal={equal} "
        f"fired_on_drop={fired_on_drop} nested_equal={nested_equal} "
        f"identity_set_equal={key_equal}"
    )
    if not out["pass"]:
        print("FAILED:IMP-0152-probe2 candidate count != registry entry count")
        return 1
    print("SUCCESS:IMP-0152-probe2 candidate count equals registry entry count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
